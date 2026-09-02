import org.deidentifier.arx.ARXPopulationModel;
import org.deidentifier.arx.ARXPopulationModel.Region;
import org.deidentifier.arx.Data;
import org.deidentifier.arx.DataDefinition;
import org.deidentifier.arx.AttributeType;
import org.deidentifier.arx.risk.RiskEstimateBuilder;
import org.deidentifier.arx.risk.RiskModelPopulationUniqueness;
import org.deidentifier.arx.risk.RiskModelSampleRisks;
import org.deidentifier.arx.risk.RiskModelSampleUniqueness;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;

public class ARX30Combinations {

    // ============================================================
    // DATASET
    // ============================================================

    private static final String INPUT_FILE =
            "../../../data/validation/uci_adult/processed/adult_prepared.csv";

    private static final String OUTPUT_FILE =
            "arx_30_results_step2.csv";


    // ============================================================
    // 30 COMBINAISONS
    // ============================================================

    private static final String[][] COMBINATIONS = {

        // Niveau A : 2 QI
        {"C01", "age", "sex"},
        {"C02", "age", "race"},
        {"C03", "age", "education"},
        {"C04", "age", "occupation"},
        {"C05", "age", "native-country"},
        {"C06", "sex", "race"},
        {"C07", "sex", "education"},
        {"C08", "education", "occupation"},
        {"C09", "marital-status", "occupation"},
        {"C10", "relationship", "occupation"},

        // Niveau B : 3 QI
        {"C11", "age", "sex", "race"},
        {"C12", "age", "sex", "education"},
        {"C13", "age", "sex", "occupation"},
        {"C14", "age", "sex", "native-country"},
        {"C15", "age", "race", "native-country"},
        {"C16", "age", "education", "occupation"},
        {"C17", "age", "education", "sex"},
        {"C18", "age", "marital-status", "occupation"},
        {"C19", "age", "relationship", "occupation"},
        {"C20", "sex", "race", "native-country"},
        {"C21", "sex", "education", "occupation"},
        {"C22", "education", "occupation", "marital-status"},

        // Niveau C : 4 QI
        {"C23", "age", "sex", "race", "native-country"},
        {"C24", "age", "sex", "education", "occupation"},
        {"C25", "age", "sex", "education", "native-country"},
        {"C26", "age", "sex", "marital-status", "occupation"},
        {"C27", "age", "race", "education", "occupation"},
        {"C28", "age", "education", "occupation", "native-country"},
        {"C29", "age", "marital-status", "relationship", "occupation"},
        {"C30", "sex", "race", "education", "occupation"}
    };


    public static void main(String[] args) throws Exception {

        System.out.println("====================================================");
        System.out.println("       ARX 3.9.2 : UCI ADULT - ETAPE 2");
        System.out.println("       MESURE DE RISQUE INDEPENDANTE DE k");
        System.out.println("====================================================");

        System.out.println("Dataset : " + INPUT_FILE);

        // ========================================================
        // 1. Vérification du fichier
        // ========================================================

        File file = new File(INPUT_FILE);

        System.out.println(
                "Chemin absolu : " +
                file.getAbsolutePath()
        );

        if (!file.exists()) {
            throw new RuntimeException(
                    "Dataset introuvable : " +
                    file.getAbsolutePath()
            );
        }

        // ========================================================
        // 2. Chargement
        // ========================================================

        Data data = Data.create(
                file,
                StandardCharsets.UTF_8,
                ','
        );

        System.out.println("Dataset chargé.");

        DataDefinition definition =
                data.getDefinition();


        // ========================================================
        // 3. Configuration des QI
        // ========================================================

        String[] qiCandidates = {
                "age",
                "sex",
                "race",
                "education",
                "occupation",
                "native-country",
                "marital-status",
                "relationship"
        };

        for (String attribute : qiCandidates) {

            definition.setAttributeType(
                    attribute,
                    AttributeType.QUASI_IDENTIFYING_ATTRIBUTE
            );
        }

        definition.setAttributeType(
                "income",
                AttributeType.SENSITIVE_ATTRIBUTE
        );


        System.out.println("\n=== ATTRIBUTS CONFIGURES ===");

        System.out.println(
                "QI disponibles : " +
                definition.getQuasiIdentifyingAttributes()
        );

        System.out.println(
                "Attribut sensible : " +
                definition.getSensitiveAttributes()
        );


        // ========================================================
        // 4. Vérification DataHandle
        // ========================================================

        System.out.println("\n=== DATA HANDLE ===");

        System.out.println(
                "Nombre de colonnes : " +
                data.getHandle().getNumColumns()
        );

        for (int i = 0;
             i < data.getHandle().getNumColumns();
             i++) {

            System.out.println(
                    i + " -> " +
                    data.getHandle().getAttributeName(i)
            );
        }


        // ========================================================
        // 5. Vérification des colonnes
        // ========================================================

        System.out.println(
                "\n=== VERIFICATION DES COLONNES ==="
        );

        for (String attribute : qiCandidates) {

            int index =
                    data.getHandle().getColumnIndexOf(attribute);

            if (index == -1) {

                throw new IllegalArgumentException(
                        "La colonne '" +
                        attribute +
                        "' n'existe pas."
                );
            }

            System.out.println(
                    "OK : " +
                    attribute +
                    " -> index " +
                    index
            );
        }

        int incomeIndex =
                data.getHandle().getColumnIndexOf("income");

        if (incomeIndex == -1) {

            throw new IllegalArgumentException(
                    "La colonne 'income' n'existe pas."
            );
        }

        System.out.println(
                "OK : income -> index " +
                incomeIndex
        );


        // ========================================================
        // 6. Population
        // ========================================================

        ARXPopulationModel population =
                ARXPopulationModel.create(Region.USA);

        System.out.println(
                "\nPopulation : USA"
        );


        // ========================================================
        // 7. CSV RESULTATS
        // ========================================================

        PrintWriter csv =
                new PrintWriter(
                        new FileWriter(OUTPUT_FILE)
                );

        csv.println(
                "id," +
                "combination," +
                "num_qi," +
                "num_records," +
                "pitman," +
                "zayatz," +
                "snb," +
                "sample_unique_fraction," +
                "sample_unique_records," +
                "average_risk," +
                "highest_risk," +
                "lowest_risk," +
                "prosecutor_risk," +
                "journalist_risk," +
                "marketer_risk"
        );


        // ========================================================
        // 8. EXECUTION DES 30 COMBINAISONS
        // ========================================================

        System.out.println(
                "\n===================================================="
        );

        System.out.println(
                "              EXECUTION DES 30 TESTS"
        );

        System.out.println(
                "===================================================="
        );


        int success = 0;
        int errors = 0;


        for (String[] combination : COMBINATIONS) {

            String id = combination[0];

            System.out.println(
                    "\n--------------------------------------------"
            );

            System.out.println(
                    id + " : " +
                    buildCombinationString(combination)
            );

            System.out.println(
                    "--------------------------------------------"
            );


            try {

                // ------------------------------------------------
                // Construire l'ensemble des QI
                // ------------------------------------------------

                Set<String> qis =
                        new HashSet<>();

                for (int i = 1;
                     i < combination.length;
                     i++) {

                    qis.add(combination[i]);
                }


                // ------------------------------------------------
                // Risk estimator
                // ------------------------------------------------

                RiskEstimateBuilder builder =
                        data.getHandle().getRiskEstimator(
                                population,
                                qis
                        );

                System.out.println(
                        "Risk estimator créé."
                );


                // ------------------------------------------------
                // Population uniqueness
                // ------------------------------------------------

                RiskModelPopulationUniqueness populationRisk =
                        builder.getPopulationBasedUniquenessRisk();


                double pitman =
                        populationRisk
                                .getFractionOfUniqueTuplesPitman();

                double zayatz =
                        populationRisk
                                .getFractionOfUniqueTuplesZayatz();

                double snb =
                        populationRisk
                                .getFractionOfUniqueTuplesSNB();


                // ------------------------------------------------
                // Sample-based uniqueness
                // ------------------------------------------------

                RiskModelSampleUniqueness sampleUniqueness =
                        builder.getSampleBasedUniquenessRisk();


                double uniqueFraction =
                        sampleUniqueness
                                .getFractionOfUniqueRecords();

                double uniqueRecords =
                        sampleUniqueness
                                .getNumUniqueRecords();


                // ------------------------------------------------
                // Sample-based re-identification risk
                // ------------------------------------------------

                RiskModelSampleRisks sampleRisks =
                        builder.getSampleBasedReidentificationRisk();


                double averageRisk =
                        sampleRisks.getAverageRisk();

                double highestRisk =
                        sampleRisks.getHighestRisk();

                double lowestRisk =
                        sampleRisks.getLowestRisk();

                double prosecutorRisk =
                        sampleRisks
                                .getEstimatedProsecutorRisk();

                double journalistRisk =
                        sampleRisks
                                .getEstimatedJournalistRisk();

                double marketerRisk =
                        sampleRisks
                                .getEstimatedMarketerRisk();


                // ------------------------------------------------
                // Affichage
                // ------------------------------------------------

                System.out.println(
                        "Nombre de lignes : " +
                        data.getHandle().getNumRows()
                );

                System.out.println(
                        "Pitman : " +
                        pitman
                );

                System.out.println(
                        "Zayatz : " +
                        zayatz
                );

                System.out.println(
                        "SNB : " +
                        snb
                );

                System.out.println(
                        "Sample unique fraction : " +
                        uniqueFraction
                );

                System.out.println(
                        "Sample unique records : " +
                        uniqueRecords
                );

                System.out.println(
                        "Average re-identification risk : " +
                        averageRisk
                );

                System.out.println(
                        "Highest risk : " +
                        highestRisk
                );

                System.out.println(
                        "Lowest risk : " +
                        lowestRisk
                );

                System.out.println(
                        "Prosecutor risk : " +
                        prosecutorRisk
                );

                System.out.println(
                        "Journalist risk : " +
                        journalistRisk
                );

                System.out.println(
                        "Marketer risk : " +
                        marketerRisk
                );


                // ------------------------------------------------
                // CSV
                // ------------------------------------------------

                csv.println(
                        id + "," +
                        "\"" +
                        buildCombinationString(combination) +
                        "\"," +
                        qis.size() + "," +
                        data.getHandle().getNumRows() + "," +
                        pitman + "," +
                        zayatz + "," +
                        snb + "," +
                        uniqueFraction + "," +
                        uniqueRecords + "," +
                        averageRisk + "," +
                        highestRisk + "," +
                        lowestRisk + "," +
                        prosecutorRisk + "," +
                        journalistRisk + "," +
                        marketerRisk
                );


                success++;

            } catch (Exception e) {

                errors++;

                System.out.println(
                        "ERREUR : " +
                        e.getMessage()
                );

                csv.println(
                        id + "," +
                        "\"" +
                        buildCombinationString(combination) +
                        "\"," +
                        (combination.length - 1) +
                        ",ERROR,,,,,,,,,,"
                );
            }
        }


        // ========================================================
        // 9. FIN
        // ========================================================

        csv.close();

        System.out.println(
                "\n===================================================="
        );

        System.out.println(
                "                    FIN"
        );

        System.out.println(
                "===================================================="
        );

        System.out.println(
                "Tests réussis : " +
                success +
                " / 30"
        );

        System.out.println(
                "Tests en erreur : " +
                errors +
                " / 30"
        );

        System.out.println(
                "Résultats sauvegardés dans : " +
                new File(OUTPUT_FILE).getAbsolutePath()
        );
    }


    // ============================================================
    // UTILITAIRE
    // ============================================================

    private static String buildCombinationString(
            String[] combination) {

        StringBuilder builder =
                new StringBuilder();

        for (int i = 1;
             i < combination.length;
             i++) {

            if (i > 1) {
                builder.append(" + ");
            }

            builder.append(combination[i]);
        }

        return builder.toString();
    }
}
