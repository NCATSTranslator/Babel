#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use polars::prelude::*;
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

    // NOTE: this base implementation runs in 4ms, python version of this runs in 4s
    // let br = BufReader::new(fs::File::open(options.input).unwrap());
    //
    // let mut labels_bw = std::io::BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());
    // let mut synonyms_bw = std::io::BufWriter::new(fs::File::create(options.synonyms_output.clone().as_path()).unwrap());
    //
    // let mut used_synonyms = HashSet::new();
    //
    // for line in br.lines().skip(1) {
    //     let line = line.unwrap();
    //     let line_split = line.split("\t").collect_vec();
    //     let id = line_split.get(0).unwrap();
    //     let label = line_split.get(1).unwrap();
    //     write!(labels_bw, "ComplexPortal:{}\t{}\n", id, label).unwrap();
    //     let synonyms = line_split.get(2).unwrap();
    //     if !synonyms.to_string().eq("-") {
    //         let synonyms_split = synonyms.split("|").collect_vec();
    //         for synonym in synonyms_split.into_iter().map(|a| a.to_string()) {
    //             if !used_synonyms.contains(&synonym) {
    //                 write!(synonyms_bw, "ComplexPortal:{}\t{}\n", id, synonym).unwrap();
    //                 used_synonyms.insert(synonym);
    //             }
    //         }
    //     }
    // }

    // NOTE: this polars implementation runs in 16ms
    let usable_columns = vec!["#Complex ac", "Recommended name", "Aliases for complex"];

    let df = polars::lazy::frame::LazyCsvReader::new(options.input.clone())
        .with_separator(b'\t')
        .with_infer_schema_length(Some(0))
        .with_ignore_errors(true)
        .with_truncate_ragged_lines(true)
        .with_has_header(true)
        .finish()
        .unwrap()
        .select(usable_columns.into_iter().map(|a| col(a)).collect_vec())
        .collect()
        .unwrap();

    // println!("{}", df.head(None));

    let mut labels_df = df
        .clone()
        .lazy()
        .select([
            concat_str([lit("ComplexPortal"), col("#Complex ac")], ":", true).alias("#Complex ac"),
            col("Recommended name"),
        ])
        .collect()
        .unwrap();

    let mut file = fs::File::create(options.labels_output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut labels_df)
        .unwrap();

    let mut synonyms_df = df
        .clone()
        .lazy()
        .filter(col("Aliases for complex").neq(lit("-")))
        .select([
            concat_str([lit("ComplexPortal"), col("#Complex ac")], ":", true).alias("#Complex ac"),
            col("Aliases for complex").str().split(lit("|")).alias("Aliases for complex"),
        ])
        .explode([col("Aliases for complex")])
        .unique(Some(vec!["Aliases for complex".to_string()]), UniqueKeepStrategy::First)
        .collect()
        .unwrap();

    // println!("{}", synonyms_df.head(None));

    let mut file = fs::File::create(options.synonyms_output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut synonyms_df)
        .unwrap();

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
