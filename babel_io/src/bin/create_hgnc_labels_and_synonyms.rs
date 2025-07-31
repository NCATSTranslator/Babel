#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
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
    for gene in json_value["response"]["docs"].as_array().unwrap().into_iter() {
        let hgnc_id = gene["hgnc_id"].clone();
        let symbol = gene["symbol"].clone();
        write!(&mut labels_bw, "{}\t{}\n", hgnc_id.as_str().unwrap(), symbol.as_str().unwrap()).unwrap();

        let name = gene["name"].clone();
        write!(
            &mut synonyms_bw,
            "{}\t{}\t{}\n",
            hgnc_id.as_str().unwrap(),
            "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym",
            name.as_str().unwrap()
        )
        .unwrap();

        for alias_field in vec!["alias_symbol", "alias_name"].into_iter() {
            if !gene[alias_field].is_null() {
                let aliases = gene[alias_field].as_array().unwrap();
                for asym in aliases.into_iter() {
                    write!(
                        &mut synonyms_bw,
                        "{}\t{}\t{}\n",
                        hgnc_id.as_str().unwrap(),
                        "http://www.geneontology.org/formats/oboInOwl#hasRelatedSynonym",
                        asym.as_str().unwrap()
                    )
                    .unwrap();
                }
            }
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
