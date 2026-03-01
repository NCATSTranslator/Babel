# Release information for Babel, NodeNorm and NameRes

There are two main installations of NodeNorm that would be of interest
to users who aren't system administrators for these tools:

* ITRB Production
  * NodeNorm: <https://nodenorm.transltr.io/docs>
  * NameRes: <https://name-lookup.transltr.io/docs>
* RENCI Development
  * NodeNorm: <https://nodenormalization-sri.renci.org/docs>
  * NameRes: <https://name-resolution-sri.renci.org/docs>

## Release process and checkpoints

1. Create a new Babel release (see README.md for information).
2. Store the Babel outputs alongside other Babel releases on Hatteras.
3. Deploy a new NodeNorm instance
   1. Split the Babel outputs into smaller files to improve load times and put them on a public web
      server.
   2. Update the Translator-devops repo with the URL to these Babel output files.
   3. Create a [Redis R3 External] instance to store identifiers.
   4. Run the [NodeNorm loader] to load the Babel outputs into the redis r3 instance.
   5. Create a [NodeNorm web server] to share the data in the redis r3 instance.
4. Deploy a new NameRes instance
   1. Create an empty Apache Solr instance.
   2. Load it with synonym information from Babel outputs.
   3. Write out a Solr backup and store it as a tarball.
   4. Copy the Solr backup to a publicly accessible URL.
   5. Update the Translator-devops repo with the new URL.
   6. Create a NameRes instance that will download the Solr backup and start the instance with it
      (see [NameRes devops] for information).
5. Use the [Babel Validator] to test this release and check how it performs compared to the previous
   release.
6. Use the
   [Babel Validator Prefix Comparator](https://translatorsri.github.io/babel-validation/prefix-comparator/)
   to compare the prefix counts between releases.
7. **Check with RENCI NodeNorm users before updating RENCI NodeNorm and NameRes instances**
8. Update RENCI NodeNorm and NameRes instances.
9. Announce on Translator and RENCI channels and ask people to try it out.
10. Deploy to ITRB
    1. Use the bastion servers to delete all data from the ITRB CI Redis R3 server.
    2. Update the Translator-Devops repo and create a PR for the develop branch. Once merged, the
       new Babel outputs should be loaded into the ITRB CI Redis R3 server.
    3. Use the bastion servers to delete all data from the ITRB Test Redis R3 server.
    4. Ask ITRB to run the NodeNorm loader to populate the ITRB Test Redis R3 server.
    5. **Announce upcoming downtime to NodeNorm Prod.**
    6. Ask ITRB to take down NodeNorm Prod.
    7. Use the bastion servers to delete all data from the ITRB Prod Redis R3 server.
    8. Ask ITRB to run the NodeNorm loader to populate the ITRB Prod Redis R3 server.
    9. Ask ITRB to start the NodeNorm Prod instance.
11. Use the [Babel Validator] to test this release and check how it performs compared to the
    previous release. As a side-benefit, running these tests will warm up NameRes Solr's caches.

[Babel Validator]: https://github.com/TranslatorSRI/babel-validation
[Redis R3 External]: https://github.com/helxplatform/translator-devops/tree/ed25b5f5bfe2383ade8457da97341c90500f5291/helm/redis-r3-external
[NodeNorm loader]: https://github.com/helxplatform/translator-devops/tree/ed25b5f5bfe2383ade8457da97341c90500f5291/helm/node-normalization-loader
[NodeNorm web server]: https://github.com/helxplatform/translator-devops/tree/ed25b5f5bfe2383ade8457da97341c90500f5291/helm/node-normalization-web-server
[NameRes devops]: https://github.com/helxplatform/translator-devops/tree/ed25b5f5bfe2383ade8457da97341c90500f5291/helm/name-lookup
