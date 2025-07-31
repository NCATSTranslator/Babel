#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use oxigraph::io::RdfFormat;
use oxigraph::sparql::QueryResults;
use oxigraph::store::Store;
use std::error::Error;
use std::fs;
use std::fs::File;
use std::io::{BufReader, Write};
use std::path;
use std::time::Instant;

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    input: path::PathBuf,

    #[clap(short, long, required = true)]
    labels_output: path::PathBuf,

    #[clap(short, long, required = true)]
    synonyms_output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let br = BufReader::new(File::open(options.input).unwrap());
    let store = Store::new()?;
    let start_load = Instant::now();
    store
        .bulk_loader()
        .with_max_memory_size_in_megabytes(4 * 2048)
        .with_num_threads(4)
        .load_from_reader(RdfFormat::RdfXml, br)
        .expect("Could not load input");
    info!("duration to load input: {}", format_duration(start_load.elapsed()).to_string());

    let mut labels_bw = std::io::BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());
    let mut synonyms_bw = std::io::BufWriter::new(fs::File::create(options.synonyms_output.clone().as_path()).unwrap());

    let label_types = vec!["skos:prefLabel", "skos:altLabel", "rdfs:label"];

    let re = regex::Regex::new("^(.*?)(?:@[^@]*){0,1}$").unwrap();

    for label_type in label_types.into_iter() {
        let query_statement = format!(
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?x ?label WHERE {{ ?x {label_type} ?label }}"
        );
        if let QueryResults::Solutions(solutions) = store.query(query_statement.as_str())? {
            for qs in solutions.filter_map(Result::ok).into_iter() {
                let x = qs.get("x").expect("x was None");
                let mut x = x.to_string();
                x = babel_io::trim_gt_and_lt(x);

                let label = qs.get("label").expect("x was None");
                let mut label = label.to_string();
                if label.contains("@") {
                    if let Some(captures) = re.captures(label.as_str()) {
                        label = captures.get(1).unwrap().as_str().to_string();
                    }
                }

                label = babel_io::trim_quotes(label);
                label = label.trim().to_string();

                let x_split = x.split("/").collect_vec();
                let efo = x_split.last().unwrap();
                if !efo.starts_with("EFO_") {
                    continue;
                }
                let efo_split = efo.split("_").collect_vec();
                let efo_id = efo_split.last().unwrap();
                write!(synonyms_bw, "EFO:{}\t{}\t{}\n", efo_id, label_type, label).expect("Could not write triple");
                if label_type != "skos:altLabel" {
                    write!(labels_bw, "EFO:{}\t{}\n", efo_id, label).expect("Could not write triple");
                }
            }
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
