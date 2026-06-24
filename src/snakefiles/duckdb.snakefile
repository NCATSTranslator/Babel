import src.reports.duckdb_reports
import src.reports.drugprotein_conflation_report
from src.snakefiles.util import get_all_compendia, get_all_synonyms_with_drugchemicalconflated
import src.exporters.duckdb_exporters as duckdb_exporters
import os

### Write all compendia, synonym and conflation files into DuckDB databases.


# Trivial aggregation rules run locally so they don't consume a SLURM slot.
localrules:
    export_all_compendia_to_duckdb,
    export_all_synonyms_to_duckdb,
    export_all_conflations_to_duckdb,
    export_all_to_duckdb,
    all_duckdb_reports,


# Write all compendia files to DuckDB and Parquet, then create `babel_outputs/duckdb/compendia_done` to signal that we're done.
rule export_all_compendia_to_duckdb:
    input:
        compendium_duckdb_files=expand(
            "{od}/duckdb/duckdbs/filename={fn}/compendium.duckdb",
            od=config["output_directory"],
            fn=map(lambda fn: os.path.splitext(fn)[0], get_all_compendia(config)),
        ),
    output:
        x=config["output_directory"] + "/duckdb/compendia_done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the Parquet files for a particular compendia file.
rule export_compendia_to_duckdb:
    input:
        compendium_file=config["output_directory"] + "/compendia/{filename}.txt",
    output:
        duckdb_filename=config["output_directory"] + "/duckdb/duckdbs/filename={filename}/compendium.duckdb",
        node_parquet_file=config["output_directory"] + "/duckdb/parquet/filename={filename}/Node.parquet",
        clique_parquet_file=config["output_directory"] + "/duckdb/parquet/filename={filename}/Clique.parquet",
        edge_parquet_file=config["output_directory"] + "/duckdb/parquet/filename={filename}/Edge.parquet",
    benchmark:
        config["output_directory"] + "/benchmarks/export_compendia_to_duckdb_{filename}.tsv"
    resources:
        runtime="6h",
        mem="512G",
    run:
        print(f"Exporting {input.compendium_file} to {output.duckdb_filename}...")
        duckdb_exporters.export_compendia_to_parquet(
            input.compendium_file, output.clique_parquet_file, output.edge_parquet_file, output.duckdb_filename
        )


# Write all synonyms files to Parquet via DuckDB, then create `babel_outputs/duckdb/synonyms_done` to signal that we're done.
rule export_all_synonyms_to_duckdb:
    input:
        synonyms_duckdb_files=expand(
            "{od}/duckdb/duckdbs/filename={fn}/synonyms.duckdb",
            od=config["output_directory"],
            fn=map(lambda fn: os.path.splitext(fn)[0], get_all_synonyms_with_drugchemicalconflated(config)),
        ),
    output:
        x=config["output_directory"] + "/duckdb/synonyms_done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the Parquet files for a particular compendia file.
rule export_synonyms_to_duckdb:
    input:
        synonyms_file=config["output_directory"] + "/synonyms/{filename}.txt.gz",
    output:
        duckdb_filename=config["output_directory"] + "/duckdb/duckdbs/filename={filename}/synonyms.duckdb",
        synonyms_parquet_filename=config["output_directory"] + "/duckdb/parquet/filename={filename}/Synonyms.parquet",
    benchmark:
        config["output_directory"] + "/benchmarks/export_synonyms_to_duckdb_{filename}.tsv"
    resources:
        # Protein and GeneProteinConflated have hundreds of UniProt synonyms
        # per entry; after unnesting the names array the row count is large
        # enough to OOM at 128G.
        mem=lambda wildcards: "512G" if wildcards.filename in ("Protein", "GeneProteinConflated") else "128G",
        runtime="3h",
    run:
        # Cap DuckDB at 75% of the SLURM allocation so Python + OS overhead
        # don't push total RSS over the job limit. Without this, DuckDB
        # auto-sizes to 75% of *total system* RAM, which can far exceed the
        # SLURM allocation on a multi-tenant HPC node.
        # resources.mem is a string like "128G" or "512G"; parse to MB.
        duckdb_memory_limit_mb = int(int(resources.mem.rstrip("G")) * 1024 * 0.75)
        duckdb_exporters.export_synonyms_to_parquet(
            input.synonyms_file,
            output.duckdb_filename,
            output.synonyms_parquet_filename,
            memory_limit_mb=duckdb_memory_limit_mb,
        )


# Write all conflation files to Parquet via DuckDB.
rule export_all_conflations_to_duckdb:
    input:
        conflation_parquet_files=expand(
            "{od}/duckdb/parquet/filename={cn}/Conflation.parquet",
            od=config["output_directory"],
            cn=[os.path.splitext(fn)[0] for fn in config["geneprotein_outputs"] + config["drugchemical_outputs"]],
        ),
    output:
        x=config["output_directory"] + "/duckdb/conflations_done",
    shell:
        "echo 'done' >> {output.x}"


# Generic rule for generating the Parquet file for a single conflation file.
rule export_conflation_to_duckdb:
    input:
        conflation_file=config["output_directory"] + "/conflation/{conflation_name}.txt",
    output:
        duckdb_filename=config["output_directory"] + "/duckdb/duckdbs/filename={conflation_name}/conflation.duckdb",
        parquet_filename=config["output_directory"] + "/duckdb/parquet/filename={conflation_name}/Conflation.parquet",
    benchmark:
        config["output_directory"] + "/benchmarks/export_conflation_to_duckdb_{conflation_name}.tsv"
    run:
        duckdb_exporters.export_conflation_to_parquet(
            input.conflation_file, wildcards.conflation_name, output.duckdb_filename, output.parquet_filename
        )


# Create `babel_outputs/duckdb/done` once all the files have been converted.
rule export_all_to_duckdb:
    input:
        compendia_done=config["output_directory"] + "/duckdb/compendia_done",
        synonyms_done=config["output_directory"] + "/duckdb/synonyms_done",
        conflations_done=config["output_directory"] + "/duckdb/conflations_done",
    output:
        x=config["output_directory"] + "/duckdb/done",
    shell:
        "echo 'done' >> {output.x}"


# There are some reports we want to run on the Parquet files that have been generated.
rule check_for_identically_labeled_cliques:
    input:
        config["output_directory"] + "/duckdb/done",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/identically_labeled_clique.duckdb"),
        identically_labeled_cliques_tsv=config["output_directory"]
        + "/reports/duckdb/identically_labeled_cliques.tsv.gz",
    benchmark:
        config["output_directory"] + "/benchmarks/check_for_identically_labeled_cliques.tsv"
    resources:
        # This rule keeps dying with `bad allocation` failing a ~8 MB allocation, and the
        # address-space snapshot pins the cause beyond doubt: mappings=65532 against the kernel's
        # vm.max_map_count=65530 -- an mmap-count limit, NOT a RAM shortage (cgroup peak 85 GiB of a
        # 500 GiB limit, Committed_AS 80 GiB of 1359 GiB). Disabling DuckDB's external file cache did
        # NOT change the count, so the mappings are DuckDB's buffer-pool allocations: VmSize (84.8
        # GiB) tracks the query's peak memory at ~1.3 MB per mapping, and DuckDB's allocator retains
        # the mappings after freeing the pages (cgroup current falls but VmSize/mappings stay at the
        # peak). The mapping count therefore scales with peak buffer-pool memory, which is bounded by
        # memory_limit. So cap memory_limit far below the query's natural ~85 GiB peak: at 16G the
        # spillable two-pass query holds only ~16 GiB of buffers at once (~12k mappings, comfortably
        # under 65530), spilling the rest to disk. The definitive fix is for the cluster to raise
        # vm.max_map_count (issue #846); this keeps the rule running until then. See slurm/README.md.
        mem="512G",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    run:
        src.reports.duckdb_reports.check_for_identically_labeled_cliques(
            params.parquet_dir,
            output.duckdb_filename,
            output.identically_labeled_cliques_tsv,
            {
                "memory_limit": "16G",
                "threads": 1,
                "preserve_insertion_order": False,
            },
        )


rule check_for_duplicate_curies:
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/duplicate_curies.duckdb"),
        duplicate_curies=config["output_directory"] + "/reports/duckdb/duplicate_curies.tsv",
    benchmark:
        config["output_directory"] + "/benchmarks/check_for_duplicate_curies.tsv"
    resources:
        # Pass 1 is a GROUP BY over every CURIE in the full Edge set (~1B distinct groups) and is
        # the memory bottleneck; the two-pass rewrite does not shrink it. On the 1.17 graph this
        # rule died with `terminate called ... bad allocation`: a *background-thread* DuckDB OOM
        # (only possible with threads > 1) that aborts the process with SIGABRT, and an untracked
        # allocation that overshot the cgroup hard limit because memory_limit 1400G left only ~13%
        # headroom under mem 1500G. It now follows the same safe recipe as its report siblings:
        # single-threaded (no uncatchable background-thread OOM, no per-thread hash-table
        # multiplication) with memory_limit (1000G) well below mem (1500G) for headroom, and a
        # large temp dir so the spillable pass-1 aggregate spills instead of falling back to RAM.
        mem="1500G",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    run:
        src.reports.duckdb_reports.check_for_duplicate_curies(
            params.parquet_dir,
            output.duckdb_filename,
            output.duplicate_curies,
            {
                "memory_limit": "1000G",
                "threads": 1,
                "preserve_insertion_order": False,
                "max_temp_directory_size": "1500GB",
            },
        )


rule check_for_duplicate_clique_leaders:
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/duplicate_clique_leaders.duckdb"),
        duplicate_clique_leaders_tsv=config["output_directory"] + "/reports/duckdb/duplicate_clique_leaders.tsv",
    benchmark:
        config["output_directory"] + "/benchmarks/check_for_duplicate_clique_leaders.tsv"
    resources:
        # The two-pass query keeps peak memory low, but stay generous so the spillable
        # pass-1 aggregation does not have to fall back to the (NFS-backed) temp directory.
        mem="512G",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    run:
        src.reports.duckdb_reports.check_for_duplicate_clique_leaders(
            params.parquet_dir,
            output.duckdb_filename,
            output.duplicate_clique_leaders_tsv,
            {
                "memory_limit": "400G",
                "threads": 4,
                "preserve_insertion_order": False,
            },
        )


rule generate_curie_report:
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/curie_report.duckdb"),
        curie_report_json=config["output_directory"] + "/reports/duckdb/curie_report.json",
    benchmark:
        config["output_directory"] + "/benchmarks/generate_curie_report.tsv"
    resources:
        # The distinct counts use approx_count_distinct() (a fixed-size HLL sketch per group)
        # instead of an exact, non-spillable COUNT(DISTINCT) that OOMed over the full Edge set.
        # memory_limit is kept well below mem for headroom under the cgroup hard limit; single
        # thread keeps per-thread state low. See slurm/README.md.
        mem="1500G",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    run:
        src.reports.duckdb_reports.generate_curie_report(
            params.parquet_dir,
            output.duckdb_filename,
            output.curie_report_json,
            {
                "memory_limit": "1000G",
                "threads": 1,
                "preserve_insertion_order": False,
            },
        )


rule generate_clique_leader_report:
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/clique_leaders.duckdb"),
        clique_leaders_json=config["output_directory"] + "/reports/duckdb/clique_leaders.json",
    benchmark:
        config["output_directory"] + "/benchmarks/generate_clique_leader_report.tsv"
    resources:
        # The distinct counts use approx_count_distinct() (a fixed-size HLL sketch per group)
        # instead of an exact, non-spillable COUNT(DISTINCT) that OOMed over the full Edge set.
        # memory_limit is kept well below mem for headroom under the cgroup hard limit; single
        # thread keeps per-thread state low. See slurm/README.md.
        mem="1500G",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
    run:
        src.reports.duckdb_reports.generate_clique_leaders_report(
            params.parquet_dir,
            output.duckdb_filename,
            output.clique_leaders_json,
            {
                "memory_limit": "1000G",
                "threads": 1,
                "preserve_insertion_order": False,
            },
        )


# Estimate a prospective DrugProtein conflation (issue #706). This does not change any compendium;
# it resolves both endpoints of the existing DrugChemical bridge concords to their clique leaders
# and counts the pairs that cross the protein/chemical boundary -- exactly the pairs DrugChemical
# conflation discards today. See src/reports/drugprotein_conflation_report.py and docs/Conflation.md.
rule drugprotein_conflation_estimate:
    input:
        config["output_directory"] + "/duckdb/done",
        config["output_directory"] + "/duckdb/compendia_done",
        rxnorm_concord=config["intermediate_directory"] + "/drugchemical/concords/RXNORM",
        umls_concord=config["intermediate_directory"] + "/drugchemical/concords/UMLS",
        pubchem_concord=config["intermediate_directory"] + "/drugchemical/concords/PUBCHEM_RXNORM",
        manual_concord=config["input_directory"] + "/manual_concords/drugchemical.tsv",
    output:
        duckdb_filename=temp(config["output_directory"] + "/duckdb/duckdbs/drugprotein_conflation_estimate.duckdb"),
        summary_json=config["output_directory"] + "/reports/drugprotein/summary.json",
        edges_tsv_gz=config["output_directory"] + "/reports/drugprotein/bridge_edges.tsv.gz",
        top_cliques_csv=config["output_directory"] + "/reports/drugprotein/top_cliques.csv",
    benchmark:
        config["output_directory"] + "/benchmarks/drugprotein_conflation_estimate.tsv"
    resources:
        # The Edge scan is restricted to the bridge prefixes up front and the cross-pipeline pair
        # set is small, so this is far lighter than the full-graph reports; memory_limit is still
        # kept well below mem for cgroup headroom. See slurm/README.md.
        mem="512G",
    params:
        parquet_dir=config["output_directory"] + "/duckdb/parquet/",
        protein_filenames=[os.path.splitext(f)[0] for f in config["protein_outputs"]],
        chemical_filenames=[os.path.splitext(f)[0] for f in config["chemical_outputs"]],
    run:
        src.reports.drugprotein_conflation_report.estimate_drugprotein_conflation(
            params.parquet_dir,
            [
                ("drugchemical/RXNORM", input.rxnorm_concord),
                ("drugchemical/UMLS", input.umls_concord),
                ("drugchemical/PUBCHEM_RXNORM", input.pubchem_concord),
            ],
            input.manual_concord,
            output.duckdb_filename,
            output.summary_json,
            output.edges_tsv_gz,
            output.top_cliques_csv,
            protein_filenames=params.protein_filenames,
            chemical_filenames=params.chemical_filenames,
            duckdb_config={
                "memory_limit": "400G",
                "threads": 1,
                "preserve_insertion_order": False,
            },
        )


rule all_duckdb_reports:
    input:
        config["output_directory"] + "/duckdb/done",
        identically_labeled_cliques_tsv=config["output_directory"]
        + "/reports/duckdb/identically_labeled_cliques.tsv.gz",
        duplicate_curies=config["output_directory"] + "/reports/duckdb/duplicate_curies.tsv",
        duplicate_clique_leaders_tsv=config["output_directory"] + "/reports/duckdb/duplicate_clique_leaders.tsv",
        curie_report_json=config["output_directory"] + "/reports/duckdb/curie_report.json",
        by_clique_report_json=config["output_directory"] + "/reports/duckdb/clique_leaders.json",
        drugprotein_summary_json=config["output_directory"] + "/reports/drugprotein/summary.json",
    output:
        x=config["output_directory"] + "/reports/duckdb/done",
    shell:
        "echo 'done' >> {output.x}"
