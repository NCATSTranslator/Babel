//! Rust replacement for `babel_utils.glom()` — union-find clique building.
//!
//! The Python original copies the whole merged clique on every group (`set().union(...)`), re-scans
//! it for the `unique_prefixes` / `KEGG` / `PUBCHEM` / `close` checks, and reassigns every member —
//! O(clique) per merge, O(N²) for a clique that grows to N one merge at a time.
//!
//! This version interns every CURIE to a `u32` and runs a disjoint-set forest with path
//! compression and union by size. Constraint metadata (per-unique-prefix member counts, a
//! garbage-prefix flag) is maintained incrementally at each root so the checks are
//! O(#unique_prefixes), not O(clique). Merged cliques grow the *larger* Python `set` in place and
//! only the *smaller* side's members are reassigned in the dict, so an identifier is reassigned at
//! most log2(N) times across a build and total dict writes are O(N log N).
//!
//! Semantics preserved exactly from the Python implementation:
//! - Group order is significant: a `unique_prefixes` / `close` rejection depends on the clique state
//!   at that point, so the merge loop is sequential (see the module docs on parallelism).
//! - A rejected group leaves the state untouched; in particular its *new* members are NOT added. This
//!   is enforced with a `present` flag distinct from interning, so a member first seen in a rejected
//!   group is still "new" for later groups.
//! - The `KEGG`/`PUBCHEM` guard always raises (it is not debug-gated in the Python). It is computed
//!   from per-root flags so a garbage identifier already present in a seeded clique is still caught
//!   when a group first touches that clique.
//! - `close=` is honored (currently a no-op in `diseasephenotype`, but implemented faithfully).
//! - The `pref` parameter is accepted and ignored (its only Python use is a `pass`-bodied loop).
//! - Elements may be `str` or `LabeledID` (the latter via its `.identifier` attribute).

use parking_lot::Mutex;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PySet, PyString};
use rayon::prelude::*;
use rustc_hash::{FxBuildHasher, FxHashMap, FxHasher};
use std::hash::{Hash, Hasher};
use std::sync::LazyLock;

/// Owned form of the `close=` argument: for each close prefix, a map of identifier -> partner list.
type ClosePartners = FxHashMap<String, Vec<String>>;
type CloseData = Vec<(String, ClosePartners)>;

/// A cached `Glom` state for one `conc_set` dict, so the hot-caller pattern (one `glom` call per
/// file on the SAME dict) does not re-read and re-intern the whole state every call. `_dict` is a
/// strong reference keeping the dict (hence its address) alive while cached, so the address cannot
/// be reused by a different dict and a cache hit at that key really is the same object.
struct CacheEntry {
    _dict: Py<PyDict>,
    glom: Glom,
    /// Number of entries in `conc_set` when this state was stored; a mismatch with the live dict's
    /// length means something mutated it outside `glom`, so we rebuild instead.
    present_count: usize,
    /// The `unique_prefixes` this state was built with; a change invalidates the per-root counts.
    ups: Vec<String>,
}

/// Cross-call cache keyed by the dict's address. Bounded: on overflow we simply clear it (a dropped
/// entry only means the next call rebuilds, which is always correct). All access happens with the
/// GIL held (glom calls are serialized by Python), so dropping the `Py` references here is safe.
static CACHE: LazyLock<parking_lot::Mutex<std::collections::HashMap<usize, CacheEntry>>> =
    LazyLock::new(|| parking_lot::Mutex::new(std::collections::HashMap::new()));

/// Maximum number of dicts to keep cached before clearing the whole cache.
const CACHE_CAP: usize = 32;

/// The two prefixes the original treats as "garbage" and raises on. Compared against the exact
/// `split(':')[0]` prefix, so `KEGG.COMPOUND` / `PUBCHEM.COMPOUND` do NOT match — only bare
/// `KEGG:` / `PUBCHEM:` do, exactly like the Python.
const GARBAGE_PREFIXES: &[&str] = &["KEGG", "PUBCHEM"];

/// FxHash of a string (simple, fast, non-cryptographic — fine for short ASCII CURIEs).
fn fxhash_of(s: &str) -> usize {
    let mut h = FxHasher::default();
    s.hash(&mut h);
    h.finish() as usize
}

/// Sharded interner used to build the initial CURIE→id map in parallel. Each shard owns a sub-map
/// guarded by its own mutex, so rayon threads only contend when they hash into the same shard.
/// The id assignment order is timing-dependent, but ids are internal — the observable output (cliques
/// as sets of CURIE strings) does not depend on which integer a CURIE got.
struct ShardedInterner {
    shards: Vec<Mutex<FxHashMap<String, u32>>>,
    /// `strings[i]` is the CURIE that got id `i`. The id IS the index, assigned under this lock, so
    /// `strings` and the per-shard maps stay consistent.
    strings: Mutex<Vec<String>>,
}

impl ShardedInterner {
    fn new(num_shards: usize) -> Self {
        let mut shards = Vec::with_capacity(num_shards);
        for _ in 0..num_shards {
            shards.push(Mutex::new(FxHashMap::default()));
        }
        Self {
            shards,
            strings: Mutex::new(Vec::new()),
        }
    }

    /// Get-or-assign an id for `curie`. Safe to call from many threads.
    fn intern(&self, curie: &str) -> u32 {
        let shard_idx = fxhash_of(curie) % self.shards.len();
        // Fast path: already present.
        {
            let map = self.shards[shard_idx].lock();
            if let Some(&id) = map.get(curie) {
                return id;
            }
        }
        // Slow path: re-check under the shard lock, then assign. Lock order is shard -> strings,
        // always, so no deadlock across threads on different shards.
        let mut map = self.shards[shard_idx].lock();
        if let Some(&id) = map.get(curie) {
            return id;
        }
        let mut strings = self.strings.lock();
        let id = strings.len() as u32;
        strings.push(curie.to_string());
        map.insert(curie.to_string(), id);
        id
    }

    /// Consume the interner, returning `(id_of, strings)` with `strings[id] == curie`.
    fn into_parts(self) -> (FxHashMap<String, u32>, Vec<String>) {
        let strings = self.strings.into_inner();
        let mut id_of = FxHashMap::with_capacity_and_hasher(strings.len(), FxBuildHasher);
        for (i, s) in strings.iter().enumerate() {
            id_of.insert(s.clone(), i as u32);
        }
        (id_of, strings)
    }
}

/// The clique-builder state. One of these corresponds to one `conc_set` dict.
pub struct Glom {
    // --- interning ---
    id_of: FxHashMap<String, u32>,
    curie: Vec<String>,      // id -> CURIE string
    prefix_of: Vec<u32>,     // id -> prefix id
    prefix_str: Vec<String>, // prefix id -> prefix string
    prefix_id_of: FxHashMap<String, u32>,

    // --- union-find ---
    parent: Vec<u32>,
    size: Vec<u32>,
    /// `present[id]` = true iff this id is currently part of the clique state (has a dict entry).
    /// Distinct from "interned" so that a member first seen in a *rejected* group stays new.
    present: Vec<bool>,

    // --- per-root constraint metadata (meaningful only at roots) ---
    /// `up_count[root][i]` = number of members whose prefix equals `unique_prefixes[i]`.
    up_count: Vec<Vec<u32>>,
    /// `garbage[root]` = the clique contains a KEGG/PUBCHEM-prefixed member.
    garbage: Vec<bool>,
    /// The live Python set object for each root (grown in place on merge).
    py_set: Vec<Option<Py<PySet>>>,

    // --- unique-prefix config for this state ---
    unique_prefix_ids: Vec<u32>,
    /// prefix id -> position in `unique_prefix_ids` (if it is a unique prefix).
    up_position: FxHashMap<u32, usize>,
    /// prefix ids that are garbage.
    garbage_prefix_ids: Vec<u32>,
}

impl Glom {
    /// Build state by reading an existing `conc_set` dict (the drop-in entry path). Groups the dict's
    /// identifiers by their shared set object to reconstruct the partition, and builds the CURIE→id
    /// interning table in parallel via a sharded interner.
    fn build_from_conc_set(
        py: Python<'_>,
        conc_set: &Bound<'_, PyDict>,
        unique_prefixes: &[String],
    ) -> PyResult<Glom> {
        // 1. Extract (curie, set_ptr, set_obj) triples from the dict. This is the GIL-bound read.
        let mut triples: Vec<(String, usize, Py<PySet>)> = Vec::with_capacity(conc_set.len());
        for (k, v) in conc_set.iter() {
            let curie: String = k.extract()?;
            let set_bound = v.downcast::<PySet>()?;
            let ptr = set_bound.as_ptr() as usize;
            triples.push((curie, ptr, set_bound.clone().unbind()));
        }

        // 2. Intern all CURIEs in parallel (sharded map), then take the deterministic id table.
        let curies: Vec<String> = triples.iter().map(|(c, _, _)| c.clone()).collect();
        let interner = ShardedInterner::new(64);
        curies.par_iter().for_each(|c| {
            interner.intern(c);
        });
        let (id_of, strings) = interner.into_parts();

        let mut g = Glom::with_capacity(strings.len(), unique_prefixes);
        g.id_of = id_of;
        g.curie = strings;
        // Append per-id prefix + union-find singleton rows, in id order.
        for id in 0..g.curie.len() as u32 {
            g.finish_intern_existing(id);
        }

        // 3. Group ids by set object, union each clique, and record the live set per root.
        let mut by_set: FxHashMap<usize, (Py<PySet>, Vec<u32>)> = FxHashMap::default();
        for (curie, ptr, set_obj) in triples {
            let id = g.id_of[curie.as_str()];
            by_set
                .entry(ptr)
                .or_insert((set_obj, Vec::new()))
                .1
                .push(id);
        }
        for (_ptr, (set_obj, ids)) in by_set {
            if ids.is_empty() {
                continue;
            }
            let root = ids[0];
            for &id in &ids {
                g.present[id as usize] = true;
            }
            for &id in &ids[1..] {
                g.parent[id as usize] = root;
                g.size[root as usize] += g.size[id as usize];
                let k = g.unique_prefix_ids.len();
                for i in 0..k {
                    g.up_count[root as usize][i] += g.up_count[id as usize][i];
                }
                g.garbage[root as usize] |= g.garbage[id as usize];
            }
            g.py_set[root as usize] = Some(set_obj);
        }
        let _ = py;
        Ok(g)
    }

    /// Create an empty state with the unique-prefix config prepared.
    fn with_capacity(n: usize, unique_prefixes: &[String]) -> Glom {
        let mut g = Glom {
            id_of: FxHashMap::with_capacity_and_hasher(n, FxBuildHasher),
            curie: Vec::with_capacity(n),
            prefix_of: Vec::with_capacity(n),
            prefix_str: Vec::new(),
            prefix_id_of: FxHashMap::default(),
            parent: Vec::with_capacity(n),
            size: Vec::with_capacity(n),
            present: Vec::with_capacity(n),
            up_count: Vec::with_capacity(n),
            garbage: Vec::with_capacity(n),
            py_set: Vec::with_capacity(n),
            unique_prefix_ids: Vec::with_capacity(unique_prefixes.len()),
            up_position: FxHashMap::default(),
            garbage_prefix_ids: Vec::new(),
        };
        // Intern the configured unique prefixes and record their positions.
        for up in unique_prefixes {
            let pid = g.intern_prefix(up);
            let pos = g.unique_prefix_ids.len();
            g.unique_prefix_ids.push(pid);
            g.up_position.insert(pid, pos);
        }
        for gp in GARBAGE_PREFIXES {
            let pid = g.intern_prefix(gp);
            g.garbage_prefix_ids.push(pid);
        }
        g
    }

    fn intern_prefix(&mut self, prefix: &str) -> u32 {
        if let Some(&pid) = self.prefix_id_of.get(prefix) {
            return pid;
        }
        let pid = self.prefix_str.len() as u32;
        self.prefix_str.push(prefix.to_string());
        self.prefix_id_of.insert(prefix.to_string(), pid);
        pid
    }

    /// Append the union-find singleton row for an already-interned id (used during the parallel
    /// build, where `id_of`/`curie` were populated up front).
    fn finish_intern_existing(&mut self, id: u32) {
        let prefix: String = Self::prefix_of_curie(&self.curie[id as usize]).to_string();
        let pid = self.intern_prefix(&prefix);
        self.prefix_of.push(pid);
        self.parent.push(id);
        self.size.push(1);
        self.present.push(false);
        let k = self.unique_prefix_ids.len();
        let mut uc = vec![0u32; k];
        if let Some(&pos) = self.up_position.get(&pid) {
            uc[pos] = 1;
        }
        self.up_count.push(uc);
        self.garbage.push(self.garbage_prefix_ids.contains(&pid));
        self.py_set.push(None);
    }

    fn prefix_of_curie(curie: &str) -> &str {
        curie.split(':').next().unwrap_or(curie)
    }

    /// Intern a CURIE, assigning a fresh id + singleton union-find row if unseen.
    fn intern(&mut self, curie: &str) -> u32 {
        if let Some(&id) = self.id_of.get(curie) {
            return id;
        }
        let id = self.curie.len() as u32;
        self.id_of.insert(curie.to_string(), id);
        self.curie.push(curie.to_string());
        self.finish_intern_existing(id);
        id
    }

    fn is_garbage_id(&self, id: u32) -> bool {
        self.garbage_prefix_ids
            .contains(&self.prefix_of[id as usize])
    }

    /// Path halving — amortized O(α(n)).
    fn find(&mut self, mut x: u32) -> u32 {
        while self.parent[x as usize] != x {
            let p = self.parent[x as usize];
            self.parent[x as usize] = self.parent[p as usize];
            x = self.parent[x as usize];
        }
        x
    }

    /// O(#unique_prefixes): would merging these roots + new members put >1 member of some unique
    /// prefix into one clique?
    fn would_violate_unique(&self, roots: &[u32], new_members: &[u32]) -> bool {
        let k = self.unique_prefix_ids.len();
        if k == 0 {
            return false;
        }
        let mut totals = vec![0u32; k];
        for &r in roots {
            let uc = &self.up_count[r as usize];
            for i in 0..k {
                totals[i] += uc[i];
            }
        }
        for &id in new_members {
            if let Some(&pos) = self.up_position.get(&self.prefix_of[id as usize]) {
                totals[pos] += 1;
            }
        }
        totals.iter().any(|&t| t > 1)
    }

    /// Materialize the prospective clique's member strings (involved roots' sets + new members) for
    /// the `close` check. Only called when `close` is non-empty.
    fn prospective_members(
        &self,
        py: Python<'_>,
        roots: &[u32],
        new_members: &[u32],
    ) -> PyResult<(Vec<String>, rustc_hash::FxHashSet<String>)> {
        let mut members: Vec<String> = Vec::new();
        let mut seen = rustc_hash::FxHashSet::default();
        for &r in roots {
            if let Some(pyset) = &self.py_set[r as usize] {
                let bound = pyset.bind(py);
                for m in bound.iter() {
                    let s: String = m.extract()?;
                    if seen.insert(s.clone()) {
                        members.push(s);
                    }
                }
            }
        }
        for &id in new_members {
            let s = self.curie[id as usize].clone();
            if seen.insert(s.clone()) {
                members.push(s);
            }
        }
        Ok((members, seen))
    }

    /// Faithful `close` check: for each `(cpref, closedict)`, find prospective members starting with
    /// `cpref`; for each, if any of `closedict[pident]`'s partners is also in the prospective clique,
    /// reject. Missing `closedict` keys behave like the caller's `defaultdict(set)` (empty).
    fn would_violate_close(
        &self,
        py: Python<'_>,
        roots: &[u32],
        new_members: &[u32],
        close: &CloseData,
    ) -> PyResult<bool> {
        if close.is_empty() {
            return Ok(false);
        }
        let (members, member_set) = self.prospective_members(py, roots, new_members)?;
        for (cpref, closedict) in close {
            for m in &members {
                if !m.starts_with(cpref.as_str()) {
                    continue;
                }
                if let Some(partners) = closedict.get(m) {
                    for p in partners {
                        if member_set.contains(p) {
                            return Ok(true);
                        }
                    }
                }
            }
        }
        Ok(false)
    }

    /// Process one group (1–2 already-interned member ids). Mutates `conc_set` in place on merge.
    /// Returns Err for the KEGG/PUBCHEM guard; Ok(true) if merged, Ok(false) if rejected.
    fn add_group(
        &mut self,
        py: Python<'_>,
        conc_set: &Bound<'_, PyDict>,
        group: &[u32],
        close: &CloseData,
    ) -> PyResult<bool> {
        // Split into roots of present members vs genuinely-new members.
        let mut roots: Vec<u32> = Vec::new();
        let mut new_members: Vec<u32> = Vec::new();
        for &id in group {
            if self.present[id as usize] {
                let r = self.find(id);
                if !roots.contains(&r) {
                    roots.push(r);
                }
            } else if !new_members.contains(&id) {
                new_members.push(id);
            }
        }

        // Garbage guard (always raises, like the Python). Involved roots' flag + new members.
        let mut garbage = roots.iter().any(|&r| self.garbage[r as usize]);
        if !garbage {
            garbage = new_members.iter().any(|&id| self.is_garbage_id(id));
        }
        if garbage {
            return Err(PyException::new_err("garbage"));
        }

        // unique_prefixes rejection — leave state untouched.
        if self.would_violate_unique(&roots, &new_members) {
            return Ok(false);
        }
        // close rejection — leave state untouched.
        if self.would_violate_close(py, &roots, &new_members, close)? {
            return Ok(false);
        }

        self.merge(py, conc_set, &roots, &new_members)?;
        Ok(true)
    }

    /// Union the involved roots + new members into one clique, growing the largest clique's Python
    /// set in place and reassigning only the smaller sides' dict entries.
    fn merge(
        &mut self,
        py: Python<'_>,
        conc_set: &Bound<'_, PyDict>,
        roots: &[u32],
        new_members: &[u32],
    ) -> PyResult<()> {
        if roots.is_empty() {
            // All members are new: create a fresh clique rooted at the first member.
            let keeper = new_members[0];
            let set = PySet::empty(py)?;
            self.size[keeper as usize] = 0;
            let k = self.unique_prefix_ids.len();
            self.up_count[keeper as usize] = vec![0u32; k];
            self.garbage[keeper as usize] = false;
            for &id in new_members {
                self.attach_new_member(py, &set, conc_set, id, keeper)?;
            }
            self.py_set[keeper as usize] = Some(set.unbind());
            return Ok(());
        }

        // Keeper = largest involved root (union by size).
        let keeper = roots
            .iter()
            .copied()
            .max_by_key(|&r| self.size[r as usize])
            .unwrap();
        let keeper_set: Py<PySet> = self.py_set[keeper as usize]
            .as_ref()
            .expect("present root must have a live Python set")
            .clone_ref(py);
        let keeper_bound: Bound<'_, PySet> = keeper_set.bind(py).clone();

        // Absorb every other root into the keeper.
        for &r in roots {
            if r == keeper {
                continue;
            }
            self.absorb_root_into(py, &keeper_bound, conc_set, r, keeper)?;
        }
        // Add genuinely-new members to the keeper.
        for &id in new_members {
            self.attach_new_member(py, &keeper_bound, conc_set, id, keeper)?;
        }
        Ok(())
    }

    /// Move all of `src` root's members into `dst` root's (larger) clique, growing `dst_set` in place
    /// and reassigning only `src`'s members' dict entries. Then union `src` under `dst`.
    fn absorb_root_into(
        &mut self,
        py: Python<'_>,
        dst_set: &Bound<'_, PySet>,
        conc_set: &Bound<'_, PyDict>,
        src: u32,
        dst: u32,
    ) -> PyResult<()> {
        let src_set: Py<PySet> = self.py_set[src as usize]
            .as_ref()
            .expect("present root must have a live Python set")
            .clone_ref(py);
        let src_bound = src_set.bind(py);
        // Collect src's members first (we are about to orphan its set object).
        let members: Vec<Bound<'_, PyAny>> = src_bound.iter().collect();
        for m in members {
            dst_set.add(&m)?;
            conc_set.set_item(&m, dst_set)?;
        }
        // Union src under dst and fold metadata.
        self.parent[src as usize] = dst;
        self.size[dst as usize] += self.size[src as usize];
        let k = self.unique_prefix_ids.len();
        for i in 0..k {
            self.up_count[dst as usize][i] += self.up_count[src as usize][i];
        }
        self.garbage[dst as usize] |= self.garbage[src as usize];
        self.py_set[src as usize] = None; // orphan src's set object
        Ok(())
    }

    /// Add a genuinely-new member id into `dst` root's clique (growing `dst_set`, adding a dict entry).
    fn attach_new_member(
        &mut self,
        py: Python<'_>,
        dst_set: &Bound<'_, PySet>,
        conc_set: &Bound<'_, PyDict>,
        id: u32,
        dst: u32,
    ) -> PyResult<()> {
        let s = PyString::new(py, &self.curie[id as usize]);
        dst_set.add(&s)?;
        conc_set.set_item(&s, dst_set)?;
        self.present[id as usize] = true;
        if id != dst {
            self.parent[id as usize] = dst;
        }
        self.size[dst as usize] += 1;
        // This member's unique-prefix contribution, computed from its prefix rather than read from
        // `up_count[id]`. That matters when `id == dst` (the keeper of an all-new clique), whose
        // `up_count` was just reset to zeros: reading it would silently drop the keeper's own
        // contribution and defeat the unique-prefix rejection. Same reasoning for the garbage flag.
        if let Some(&pos) = self.up_position.get(&self.prefix_of[id as usize]) {
            self.up_count[dst as usize][pos] += 1;
        }
        self.garbage[dst as usize] |= self.is_garbage_id(id);
        Ok(())
    }
}

/// Extract one element of a group as a CURIE string (`str` or `LabeledID.identifier`).
fn extract_curie(elem: &Bound<'_, PyAny>) -> PyResult<String> {
    if let Ok(s) = elem.extract::<String>() {
        return Ok(s);
    }
    let ident = elem.getattr("identifier")?;
    ident.extract::<String>()
}

/// Parse the optional `close` argument into an owned form. `close` maps `cpref -> {pident -> partners}`.
fn build_close(close: Option<&Bound<'_, PyDict>>) -> PyResult<CloseData> {
    let Some(close) = close else {
        return Ok(Vec::new());
    };
    let mut out = Vec::with_capacity(close.len());
    for (cpref_obj, closedict_obj) in close.iter() {
        let cpref: String = cpref_obj.extract()?;
        let closedict = closedict_obj.downcast::<PyDict>()?;
        let mut map: ClosePartners = FxHashMap::default();
        for (pident_obj, partners_obj) in closedict.iter() {
            let pident: String = pident_obj.extract()?;
            let mut partners = Vec::new();
            for p in partners_obj.try_iter()? {
                partners.push(p?.extract::<String>()?);
            }
            map.insert(pident, partners);
        }
        out.push((cpref, map));
    }
    Ok(out)
}

/// The drop-in replacement for `babel_utils.glom()`. Mutates `conc_set` in place and returns `None`,
/// exactly like the Python implementation, so every caller keeps working unchanged.
#[pyfunction]
#[pyo3(signature = (conc_set, newgroups, unique_prefixes=None, pref=None, close=None))]
pub fn glom(
    py: Python<'_>,
    conc_set: &Bound<'_, PyDict>,
    newgroups: &Bound<'_, PyAny>,
    unique_prefixes: Option<Bound<'_, PyAny>>,
    pref: Option<String>,
    close: Option<&Bound<'_, PyDict>>,
) -> PyResult<()> {
    // vestigial: the Python only uses `pref` in a `pass`-bodied loop.
    let _ = pref;
    // `unique_prefixes` is iterated exactly like the Python (`for up in unique_prefixes`), so it may
    // be a list/tuple/set of strings or, as some callers pass, a bare string (iterated per-char).
    let ups: Vec<String> = match unique_prefixes {
        None => vec!["INCHIKEY".to_string()],
        Some(ups_obj) => {
            let mut v = Vec::new();
            for item in ups_obj.try_iter()? {
                v.push(item?.extract::<String>()?);
            }
            v
        }
    };

    // Reuse cached state for this dict if it is still valid; otherwise rebuild from the dict. This
    // is the serialization minimization for hot callers (one glom call per file on the same dict):
    // only the first call pays the full read+intern of the existing state.
    let key = conc_set.as_ptr() as usize;
    let cached = CACHE.lock().remove(&key);
    let mut g: Glom = match cached {
        Some(entry) if entry.present_count == conc_set.len() && entry.ups == ups => entry.glom,
        _ => Glom::build_from_conc_set(py, conc_set, &ups)?,
    };
    let close_data = build_close(close)?;

    for group_obj in newgroups.try_iter()? {
        let group_obj = group_obj?;
        let n = group_obj.len()?;
        if n > 2 {
            return Err(PyValueError::new_err(
                "glom() received a group with more than 2 elements",
            ));
        }
        let mut members: Vec<u32> = Vec::with_capacity(n);
        for elem in group_obj.try_iter()? {
            let curie = extract_curie(&elem?)?;
            members.push(g.intern(&curie));
        }
        g.add_group(py, conc_set, &members, &close_data)?;
    }

    // Store the state back so the next call on this dict skips the full rebuild. Bounded cache.
    let mut cache = CACHE.lock();
    if cache.len() >= CACHE_CAP {
        cache.clear();
    }
    cache.insert(
        key,
        CacheEntry {
            _dict: conc_set.clone().unbind(),
            glom: g,
            present_count: conc_set.len(),
            ups,
        },
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prefix_of_curie_splits_on_first_colon() {
        assert_eq!(
            Glom::prefix_of_curie("PUBCHEM.COMPOUND:3100"),
            "PUBCHEM.COMPOUND"
        );
        assert_eq!(Glom::prefix_of_curie("KEGG:C00001"), "KEGG");
        assert_eq!(Glom::prefix_of_curie("nocolon"), "nocolon");
    }

    #[test]
    fn garbage_prefix_is_exact_not_startswith() {
        // "PUBCHEM.COMPOUND" must NOT match the "PUBCHEM" garbage prefix.
        assert_ne!(Glom::prefix_of_curie("PUBCHEM.COMPOUND:3100"), "PUBCHEM");
        assert_eq!(Glom::prefix_of_curie("PUBCHEM:3100"), "PUBCHEM");
    }
}
