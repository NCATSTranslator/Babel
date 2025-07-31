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
    cco: path::PathBuf,

    #[clap(short, long, required = true)]
    labels_output: path::PathBuf,

    #[clap(short, long, required = true)]
    smiles_output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let store = Store::new()?;
    let start_load = Instant::now();

    // this file is small...no need for bulk loader
    let cco_br = BufReader::new(fs::File::open(options.cco).unwrap());
    store.load_from_reader(RdfFormat::Turtle, cco_br).expect("Could not load input");

    let input_br = BufReader::new(fs::File::open(options.input).unwrap());
    store
        .bulk_loader()
        .with_max_memory_size_in_megabytes(4 * 2048)
        .with_num_threads(4)
        .load_from_reader(RdfFormat::Turtle, input_br)
        .expect("Could not load input");

    info!("duration to load input: {}", format_duration(start_load.elapsed()).to_string());

    let mut labels_bw = BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());

    let query_statement = "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
             PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
             PREFIX cco: <http://rdf.ebi.ac.uk/terms/chembl#>
             SELECT ?molecule ?label
             WHERE {
                ?molecule a ?type .
                ?type rdfs:subClassOf* cco:Substance .
                ?molecule rdfs:label ?label .
            }";

    if let QueryResults::Solutions(solutions) = store.query(query_statement)? {
        for qs in solutions.filter_map(Result::ok).into_iter() {
            let iterm = qs.get("molecule").expect("molecule was None");
            let mut iterm = iterm.to_string();
            iterm = babel_io::trim_gt_and_lt(iterm);

            let iterm_split = iterm.split("/").collect_vec();
            let id = iterm_split.last().unwrap();

            let label = qs.get("label").expect("label was None");
            let mut label = label.to_string();
            label = babel_io::trim_quotes(label);

            if id.to_string() == label {
                continue;
            }
            write!(labels_bw, "CHEMBL.COMPOUND:{}\t{}\n", id, label).expect("Could not write triple");
        }
    }

    let mut smiles_bw = BufWriter::new(fs::File::create(options.smiles_output.clone().as_path()).unwrap());

    let query_statement = "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
             PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
             PREFIX cco: <http://rdf.ebi.ac.uk/terms/chembl#>
             PREFIX cheminf: <http://semanticscience.org/resource/>
             SELECT ?molecule ?smiles
             WHERE {
                ?molecule cheminf:SIO_000008 ?smile_entity .
                ?smile_entity a cheminf:CHEMINF_000018 ;
                              cheminf:SIO_000300 ?smiles .
            }";

    if let QueryResults::Solutions(solutions) = store.query(query_statement)? {
        for qs in solutions.filter_map(Result::ok).into_iter() {
            let iterm = qs.get("molecule").expect("molecule was None");
            let mut iterm = iterm.to_string();
            iterm = babel_io::trim_gt_and_lt(iterm);

            let iterm_split = iterm.split("/").collect_vec();
            let id = iterm_split.last().unwrap();

            let label = qs.get("smiles").expect("smiles was None");
            let mut label = label.to_string();
            label = babel_io::trim_quotes(label);

            write!(smiles_bw, "CHEMBL.COMPOUND:{}\t{}\n", id, label).expect("Could not write triple");
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
