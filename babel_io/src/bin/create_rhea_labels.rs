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
use std::io::{BufReader, BufWriter, Write};
use std::path;
use std::time::Instant;

// NOTE: rust runs in 13s, python runs in 21s
#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    input: path::PathBuf,

    #[clap(short, long, required = true)]
    labels_output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let br = BufReader::new(fs::File::open(options.input).unwrap());
    let store = Store::new()?;
    let start_load = Instant::now();
    store
        .bulk_loader()
        .with_max_memory_size_in_megabytes(4 * 2048)
        .with_num_threads(4)
        .load_from_reader(RdfFormat::RdfXml, br)
        .expect("Could not load input");
    info!("duration to load input: {}", format_duration(start_load.elapsed()).to_string());

    let mut labels_bw = BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());

    let query_statement = r#"PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
       PREFIX rh: <http://rdf.rhea-db.org/>
       SELECT DISTINCT ?x ?acc ?label WHERE {
         ?x rdfs:label ?label .
         ?x rh:accession ?acc .
       }"#;

    if let QueryResults::Solutions(solutions) = store.query(query_statement)? {
        for qs in solutions.filter_map(Result::ok).into_iter() {
            let iterm = qs.get("acc").expect("acc was None");
            let mut iterm = iterm.to_string();
            iterm = babel_io::trim_quotes(iterm);
            let rhea_iterm_split = iterm.split(":").collect_vec();
            let rhea_id = rhea_iterm_split.last().unwrap();

            let label = qs.get("label").expect("label was None");
            let mut label = label.to_string();
            label = babel_io::trim_quotes(label);

            write!(labels_bw, "RHEA:{}\t{}\n", rhea_id, label).expect("Could not write triple");
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
