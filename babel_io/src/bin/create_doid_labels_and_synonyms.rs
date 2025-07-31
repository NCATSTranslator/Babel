#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use serde_json::Value;
use std::error::Error;
use std::fs;
use std::io::Write;
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

    let br = std::io::BufReader::new(fs::File::open(options.input).unwrap());
    let json_value: Value = serde_json::from_reader(br)?;

    let mut labels_bw = std::io::BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());
    let mut synonyms_bw = std::io::BufWriter::new(fs::File::create(options.synonyms_output.clone().as_path()).unwrap());

    //NOTE: Python runs in 3s, rust runs < 1s
    for entry in json_value["graphs"][0]["nodes"].as_array().unwrap().into_iter() {
        if !entry["meta"].is_null() && !entry["meta"]["deprecated"].is_null() && entry["meta"]["deprecated"].as_bool().unwrap() == true {
            continue;
        }
        let doid_id = entry["id"].as_str().unwrap();
        if !doid_id.starts_with("http://purl.obolibrary.org/obo/DOID_") {
            continue;
        }
        let doid_id_split = doid_id.split("_").collect_vec();
        let doid_curie = format!("DOID:{}", doid_id_split.get(1).unwrap());

        if !entry["lbl"].is_null() {
            let label = entry["lbl"].as_str().unwrap();
            write!(&mut labels_bw, "{}\t{}\n", doid_curie, label).unwrap();
            write!(&mut synonyms_bw, "{}\tOIO:hasExactSynonym\t{}\n", doid_curie, label).unwrap();
        }

        if !entry["meta"].is_null() && !entry["meta"]["synonyms"].is_null() {
            for synonym_entry in entry["meta"]["synonyms"].as_array().unwrap().into_iter() {
                write!(
                    &mut synonyms_bw,
                    "{}\tOIO:hasExactSynonym\t{}\n",
                    doid_curie,
                    synonym_entry["val"].as_str().unwrap()
                )
                .unwrap();
            }
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
