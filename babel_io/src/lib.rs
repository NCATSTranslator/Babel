pub fn trim_gt_and_lt(mut x: String) -> String {
    if x.starts_with("<") {
        x = x.strip_prefix("<").unwrap().to_string();
    }
    if x.ends_with(">") {
        x = x.strip_suffix(">").unwrap().to_string();
    }
    x
}

pub fn trim_quotes(mut label: String) -> String {
    if label.starts_with("\"") {
        label = label.strip_prefix("\"").unwrap().to_string();
    }

    if label.ends_with("\"") {
        label = label.strip_suffix("\"").unwrap().to_string();
    }
    label
}

// extern crate core;
//
// use itertools::Itertools;
// use pyo3::prelude::*;
// use pyo3::types::PySet;
// use std::collections::{HashMap, HashSet};
// use std::fs;
// use std::fs::File;
// use std::hash::Hash;
// use std::io::prelude::*;
// use std::io::{BufRead, BufReader, BufWriter};
// use std::path::{Path, PathBuf};
//
// #[pyfunction]
// pub fn pull_uniprot_labels(input: &str, which: &str) -> PyResult<String> {
//     let input_path = PathBuf::from(input);
//
//     let output_file_name = format!("uniprot_{}.output.txt", which);
//     let mut output_path = input_path.with_file_name(output_file_name);
//     if !output_path.exists() {
//         let br = BufReader::new(File::open(input_path.as_path()).unwrap());
//         let mut bw = BufWriter::new(File::create(output_path.as_path()).unwrap());
//
//         for line in br.lines() {
//             let line = line.unwrap();
//             if !line.starts_with(">") {
//                 continue;
//             }
//             let line_split = line.split("|").collect_vec();
//             let name_split = line_split[2].split(" OS=").collect_vec();
//             let entry = format!("UniProtKB:{}\t{} ({})\n", line_split[1], name_split[0], which);
//             bw.write_all(entry.as_bytes()).unwrap();
//         }
//     }
//
//     Ok(output_path.display().to_string())
// }
//
// #[pyfunction]
// pub fn merge_uniprot_label_files(inputs: Vec<&str>, output: &str, remove_inputs: bool) -> PyResult<String> {
//     let output_path = PathBuf::from(output);
//     let mut bw = BufWriter::new(File::create(output_path.as_path()).unwrap());
//     inputs.clone().into_iter().map(|input| PathBuf::from(input)).for_each(|input_path| {
//         let br = BufReader::new(File::open(input_path.as_path()).unwrap());
//         for line in br.lines() {
//             let line = line.unwrap();
//             bw.write_all(format!("{}\n", line).as_bytes()).unwrap();
//         }
//     });
//
//     if remove_inputs {
//         inputs.iter().for_each(|input| fs::remove_file(input).unwrap());
//     }
//
//     Ok(output_path.display().to_string())
// }
//
// #[pyfunction]
// pub fn read_identifier_file(input: &str) -> PyResult<(Vec<Vec<String>>, HashMap<String, String>)> {
//     let input_path = PathBuf::from(input);
//     let br = BufReader::new(File::open(input_path.as_path()).unwrap());
//     let mut types: HashMap<String, String> = HashMap::new();
//     let mut identifiers = vec![];
//     for line in br.lines() {
//         let line = line.unwrap();
//         let x = line.trim().split('\t').collect_vec();
//         identifiers.push(vec![x[0].to_string()]);
//         if x.len() > 1 {
//             types.insert(x[0].into(), x[1].into());
//         }
//     }
//
//     Ok((identifiers, types))
// }
//
// #[pyfunction]
// pub fn glom(conc_set: HashSet<String>, newgroups: Vec<Vec<String>>, unique_prefixes: Vec<String>) -> PyResult<HashSet<String>> {
//     let mut n = 0;
//     let bad = 0;
//     let shit_prefixes = vec!["KEGG", "PUBCHEM"];
//     let test_id = "xUBERON:0002262";
//     // let mut excised = vec![];
//
//     for xgroup in newgroups {
//         if xgroup.len() > 2 {
//             println!("{:?}", xgroup);
//             panic!("nope");
//         }
//         n = n + 1;
//         if xgroup.contains(&test_id.to_string()) {
//             println!("{:?}", xgroup);
//         }
//
//         let existing_sets_w_x = xgroup
//             .clone()
//             .into_iter()
//             .filter(|x| conc_set.contains(x))
//             .map(|x| (conc_set.get(&x).unwrap(), x))
//             .collect_vec();
//
//         let existing_sets: Vec<String> = existing_sets_w_x.clone().into_iter().map(|a| a.0.clone()).collect_vec();
//         let x = existing_sets_w_x.iter().map(|a| a.1.clone()).collect_vec();
//         let mut newset = existing_sets.clone();
//         newset.dedup();
//         xgroup.iter().for_each(|a| newset.push(a.clone()));
//
//         if newset.contains(&test_id.to_string()) {
//             println!("hiset: {:?}", newset);
//             println!("input_set: {:?}", xgroup);
//             println!("esets");
//             // existing_sets.iter().for_each(|a| println!("{} {}", a, xgroup))
//         }
//
//         newset.iter().for_each(|entry| {
//             let prefix = entry.split(':').next().unwrap();
//             if shit_prefixes.contains(&prefix) {
//                 println!("entry: {}, prefix: {}", entry, prefix);
//                 panic!("garbage");
//             }
//         });
//
//         let setok = true;
//         if xgroup.contains(&test_id.to_string()) {
//             println!("setok: {}", setok);
//         }
//
//         unique_prefixes.iter().for_each(|up| {
//             if xgroup.contains(&test_id.to_string()) {
//                 println!("up: {}", up);
//             }
//             // newset.iter().filter_map(|a| );
//         });
//     }
//
//     Ok(conc_set.clone())
// }
//
// #[pymodule]
// fn babel_io(_py: Python, m: &PyModule) -> PyResult<()> {
//     m.add_function(wrap_pyfunction!(pull_uniprot_labels, m)?)?;
//     m.add_function(wrap_pyfunction!(merge_uniprot_label_files, m)?)?;
//     Ok(())
// }
//
// #[cfg(test)]
// mod tests {
//     use crate::glom;
//     use itertools::{Itertools, TupleWindows};
//     use std::collections::HashSet;
//
//     #[test]
//     fn test_glom() {
//         let local_glom = |conc_set: HashSet<String>, mut newgroups: Vec<(String, String)>, unique_prefixes: Vec<String>| -> HashSet<String> {
//             let mut n = 0;
//             let bad = 0;
//             let shit_prefixes = vec!["KEGG", "PUBCHEM"];
//             let test_id = "xUBERON:0002262";
//             // let mut excised = vec![];
//
//             for xgroup in newgroups.iter_mut() {
//                 if xgroup.len() > 2 {
//                     println!("{:?}", xgroup);
//                     panic!("nope");
//                 }
//                 n = n + 1;
//                 if xgroup.contains(&test_id.to_string()) {
//                     println!("{:?}", xgroup);
//                 }
//
//                 let existing_sets_w_x = xgroup
//                     .clone()
//                     .into_iter()
//                     .filter(|x| conc_set.contains(x))
//                     .map(|x| (conc_set.get(&x).unwrap(), x))
//                     .collect_vec();
//
//                 let existing_sets: Vec<String> = existing_sets_w_x.clone().into_iter().map(|a| a.0.clone()).collect_vec();
//                 let x = existing_sets_w_x.iter().map(|a| a.1.clone()).collect_vec();
//                 let mut newset = existing_sets.clone();
//                 newset.dedup();
//                 xgroup.iter().for_each(|a| newset.push(a.clone()));
//
//                 if newset.contains(&test_id.to_string()) {
//                     println!("hiset: {:?}", newset);
//                     println!("input_set: {:?}", xgroup);
//                     println!("esets");
//                     // existing_sets.iter().for_each(|a| println!("{} {}", a, xgroup))
//                 }
//
//                 newset.iter().for_each(|entry| {
//                     let prefix = entry.split(':').next().unwrap();
//                     if shit_prefixes.contains(&prefix) {
//                         println!("entry: {}, prefix: {}", entry, prefix);
//                         panic!("garbage");
//                     }
//                 });
//
//                 let setok = true;
//                 if xgroup.contains(&test_id.to_string()) {
//                     println!("setok: {}", setok);
//                 }
//
//                 unique_prefixes.iter().for_each(|up| {
//                     if xgroup.clcontains(&test_id.to_string()) {
//                         println!("up: {}", up);
//                     }
//                     // newset.iter().filter_map(|a| );
//                 });
//             }
//             conc_set.clone()
//         };
//
//         // let v: TupleWindows<_, (String, String)> = vec!["1", "2", "3", "4", "5", "6", "7"]
//         //     .into_iter()
//         //     .map(|a| a.to_string())
//         //     .collect_vec()
//         //     .into_iter()
//         //     .tuple_windows();
//         // println!("{:?}", v.collect::<Vec<_>>());
//         let mut conc_set = std::collections::HashSet::new();
//         let newgroups: Vec<(String, String)> = vec![
//             ("UMLS:C0000005".to_string(), String::new()),
//             ("UMLS:C0000052".to_string(), String::new()),
//             ("UMLS:C0000084".to_string(), String::new()),
//             ("UMLS:C0000107".to_string(), String::new()),
//             ("UMLS:C0000132".to_string(), String::new()),
//             ("UMLS:C0000152".to_string(), String::new()),
//             ("UMLS:C0000165".to_string(), String::new()),
//             ("UMLS:C0000184".to_string(), String::new()),
//             ("UMLS:C0000189".to_string(), String::new()),
//             ("UMLS:C0000246".to_string(), String::new()),
//             ("UMLS:C0000254".to_string(), String::new()),
//             ("UMLS:C0000257".to_string(), String::new()),
//             ("UMLS:C0000291".to_string(), String::new()),
//             ("UMLS:C0000324".to_string(), String::new()),
//             ("UMLS:C0000340".to_string(), String::new()),
//             ("UMLS:C0000353".to_string(), String::new()),
//             ("UMLS:C0000359".to_string(), String::new()),
//             ("UMLS:C0000360".to_string(), String::new()),
//         ];
//         println!("conc_set before glom: {:?}", conc_set);
//         let conc_set = local_glom(conc_set, newgroups, vec!["UniProtKB".to_string(), "PR".to_string()]);
//         println!("conc_set after glom: {:?}", conc_set);
//         // glom(d, eqs)
//         // print(f"{d}")
//         // assert len(d) == 5
//         // assert d["1"] == d["2"] == d["3"] == {"1", "2", "3"}
//         // assert d["4"] == d["5"] == {"4", "5"}
//     }
// }
