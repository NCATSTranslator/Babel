#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use std::collections::HashSet;
use std::error::Error;
use std::fs;
use std::io::{BufRead, BufReader, Write};
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

    let br = BufReader::new(fs::File::open(options.input).unwrap());

    let mut labels_bw = std::io::BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());

    let mut done = HashSet::new();

    for line in br.lines() {
        let line = line.unwrap();
        let line_split = line.split("\t").collect_vec();
        let sub_family = line_split.get(3).unwrap();
        let sub_family = sub_family.to_string();
        let main_family_split = sub_family.split(":").collect_vec();
        let main_family = main_family_split.get(0).unwrap();
        let main_family = main_family.to_string();
        let main_family_name = line_split.get(4).unwrap();
        let sub_family_name = line_split.get(5).unwrap();
        if !done.contains(&main_family) {
            write!(labels_bw, "{}\t{}\n", format!("PANTHER.FAMILY:{}", main_family), main_family_name).unwrap();
            done.insert(main_family.to_string());
        }

        if !done.contains(&sub_family) {
            write!(labels_bw, "{}\t{}\n", format!("PANTHER.FAMILY:{}", sub_family), sub_family_name).unwrap();
            done.insert(sub_family.to_string());
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
