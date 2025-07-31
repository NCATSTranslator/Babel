#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use serde_json::Value;
use std::error::Error;
use std::fs;
use std::io::{BufReader, BufWriter, Write};
use std::path;
use std::time::Instant;

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

    //NOTE: Python runs in 3s, rust runs < 1s
    let br = BufReader::new(fs::File::open(options.input).unwrap());
    let json_value: Value = serde_json::from_reader(br)?;

    let mut labels_bw = BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());

    for entry in json_value.as_array().unwrap().into_iter() {
        parse_element_for_labels(&entry, &mut labels_bw);
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}

fn parse_element_for_labels(entry: &Value, labels_bw: &mut BufWriter<fs::File>) {
    let oid = entry["stId"].as_str().unwrap();
    let name = entry["name"].as_str().unwrap();
    let species = entry["species"].as_str().unwrap();
    write!(labels_bw, "REACT:{}\t{} ({})\n", oid, name, species).unwrap();
    if !entry["children"].is_null() {
        for child_entry in entry["children"].as_array().unwrap().into_iter() {
            parse_element_for_labels(child_entry, labels_bw);
        }
    }
}
