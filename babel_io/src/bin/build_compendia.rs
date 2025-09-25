#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use oxigraph::io::RdfFormat;
use oxigraph::sparql::QueryResults;
use oxigraph::store::Store;
use std::collections::HashSet;
use std::error::Error;
use std::fs::read_to_string;
use std::io::{BufReader, BufWriter};
use std::time::Instant;
use std::{fs, path};

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    concordances: Vec<path::PathBuf>,

    #[clap(short, long, required = true)]
    identifiers: Vec<path::PathBuf>,

    #[clap(short = 'z', long, required = true)]
    ic_rdf: path::PathBuf,
}
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let dicts = HashSet::new();
    let types = HashSet::new();

    for ifile in options.identifiers {
        let asdf = read_to_string(ifile).unwrap();
        for line in asdf.lines() {}
        // new_identifiers, new_types = read_identifier_file(ifile)
        //
        //
        //
        // types = {}
        // identifiers = list()
        // with open(infile,'r') as inf:
        // for line in inf:
        //     x = line.strip().split('\t')
        // identifiers.append((x[0],))
        // if len(x) > 1:
        //     types[x[0]] = x[1]
        // return identifiers,types
        //
        //
        //
        // glom(dicts, new_identifiers, unique_prefixes=[UBERON, GO])
        // types.update(new_types)
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
