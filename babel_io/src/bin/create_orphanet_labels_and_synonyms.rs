#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use std::error::Error;
use std::fs;
use std::fs::File;
use std::io::{Read, Write};
use std::path;
use std::time::Instant;
use zip::ZipArchive;

// NOTE: do not use, utf-8 conversion issues...retaining for S&Gs

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

    let mut labels_bw = std::io::BufWriter::new(fs::File::create(options.labels_output.clone().as_path()).unwrap());
    let mut synonyms_bw = std::io::BufWriter::new(fs::File::create(options.synonyms_output.clone().as_path()).unwrap());

    let file = File::open(options.input.clone()).unwrap();
    let mut archive = ZipArchive::new(file).unwrap();

    let mut zip_file = archive.by_name("Orphanet_Nomenclature_Pack_en/ORPHAnomenclature_en.xml").unwrap();

    let mut data = vec![];
    zip_file.read_to_end(&mut data).unwrap();
    let contents = String::from_utf8_lossy(data.as_slice());

    let doc = roxmltree::Document::parse(contents.as_ref()).expect("Could not parse document");

    doc.root().descendants().filter(|n| n.tag_name().name() == "Disorder").for_each(|a| {
        let orpha_code = a.descendants().find(|b| b.tag_name().name() == "OrphaCode").unwrap().text().unwrap();
        let name = a.descendants().find(|b| b.tag_name().name() == "Name").unwrap().text().unwrap();
        let curie = format!("orphanet:{}", orpha_code);
        write!(&mut labels_bw, "{}\t{}\n", curie, name).unwrap();
        write!(&mut synonyms_bw, "{}\tOIO:hasExactSynonym\t{}\n", curie, name).unwrap();
        match a.descendants().find(|b| b.tag_name().name() == "SynonymList") {
            None => {}
            Some(all_synonyms) => {
                let all_synonyms_text = all_synonyms.text().unwrap();
                write!(&mut synonyms_bw, "{}\tOIO:hasExactSynonym\t{}\n", curie, all_synonyms_text).unwrap();
            }
        }
    });

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
