#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use polars::io::SerWriter;
use polars::prelude::{col, lit, CsvWriter, LazyFileListReader};
use std::error::Error;
use std::fs;
use std::path;
use std::time::Instant;

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    input: path::PathBuf,

    #[clap(short, long, required = true)]
    output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    // let reader = std::io::BufReader::new(fs::File::open(options.input).unwrap());
    // let mut writer = std::io::BufWriter::new(fs::File::create(options.output.clone().as_path()).unwrap());
    //
    // write!(writer, "{}\n", "UCI\tSRC_ID\tSRC_COMPOUND_ID\tASSIGNMENT").unwrap();
    //
    // for line in reader.lines().skip(1) {
    //     let line = line.unwrap();
    //     let line_split = line.trim().split("\t");
    //
    //     write!(writer, "{}\n", "UCI\tSRC_ID\tSRC_COMPOUND_ID\tASSIGNMENT").unwrap();
    // }
    let data_sources = std::collections::HashMap::from([
        ("1", "CHEMBL.COMPOUND"),
        ("2", "DRUGBANK"),
        ("4", "GTOPDB"),
        ("6", "KEGG.COMPOUND"),
        ("7", "CHEBI"),
        ("14", "UNII"),
        ("18", "HMDB"),
        ("22", "PUBCHEM.COMPOUND"),
        ("34", "DrugCentral"),
    ]);
    let re = format!("^({})$", itertools::join(data_sources.into_keys(), "|"));
    let mut df = polars::lazy::frame::LazyCsvReader::new(options.input.clone())
        .with_separator(b'\t')
        .with_infer_schema_length(Some(0))
        .with_ignore_errors(true)
        .with_truncate_ragged_lines(true)
        .with_has_header(true)
        .finish()
        .unwrap()
        .filter(col("SRC_ID").str().contains(lit(re), true))
        .filter(col("ASSIGNMENT").eq(lit("1")))
        .collect()
        .unwrap();

    let mut file = fs::File::create(options.output).expect("could not create file");
    CsvWriter::new(&mut file).include_header(true).with_separator(b'\t').finish(&mut df).unwrap();

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
