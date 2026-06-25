WITH Lengths AS (
    SELECT curie, label, LENGTH(label) AS label_length FROM Nodes
),
Examples AS (
    SELECT curie, label, label_length,
        ROW_NUMBER() OVER (PARTITION BY label_length ORDER BY label) AS rn
    FROM Lengths
)
SELECT
    label_length,
    COUNT(*) AS frequency,
    MAX(CASE WHEN rn = 1 THEN curie ELSE NULL END) AS example_curie,
    MAX(CASE WHEN rn = 1 THEN label ELSE NULL END) AS example_label
FROM Examples
GROUP BY label_length
ORDER BY label_length ASC
