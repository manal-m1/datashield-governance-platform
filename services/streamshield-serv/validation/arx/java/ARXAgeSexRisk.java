import org.deidentifier.arx.ARXPopulationModel;
import org.deidentifier.arx.ARXPopulationModel.Region;
import org.deidentifier.arx.Data;
import org.deidentifier.arx.DataDefinition;
import org.deidentifier.arx.AttributeType;
import org.deidentifier.arx.risk.RiskEstimateBuilder;
import org.deidentifier.arx.risk.RiskModelPopulationUniqueness;
import org.deidentifier.arx.io.CSVSyntax;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;

public class ARXAgeSexRisk {

    public static void main(String[] args) throws Exception {

        System.out.println("=== ARX 3.9.2 : UCI ADULT / AGE + SEX ===");

        // ----------------------------------------------------
        // 1. Dataset
        // ----------------------------------------------------

        String inputFile =
                "../../../data/validation/uci_adult/processed/adult_prepared.csv";

        System.out.println("Dataset : " + inputFile);

        // ----------------------------------------------------
        // 2. Chargement du CSV
        // ----------------------------------------------------
        // Le fichier utilise ',' comme séparateur.
        // ARX 3.9.2 demande un File pour utiliser CSVSyntax.
        // ----------------------------------------------------

        File csvFile = new File(inputFile);

        if (!csvFile.exists()) {
            throw new IllegalArgumentException(
                    "Fichier introuvable : " + csvFile.getAbsolutePath()
            );
        }

        System.out.println(
                "Chemin absolu : " + csvFile.getAbsolutePath()
        );

        CSVSyntax syntax = new CSVSyntax(
                ',',
                '"',
                '\\'
        );

        Data data = Data.create(
                csvFile,
                StandardCharsets.UTF_8,
                syntax
        );

        System.out.println("Dataset chargé.");

        DataDefinition definition = data.getDefinition();

        // ----------------------------------------------------
        // 3. Configuration des attributs ARX
        // ----------------------------------------------------

        System.out.println("\n=== ATTRIBUTS ARX ===");

        System.out.println(
                "QI avant configuration : " +
                definition.getQuasiIdentifyingAttributes()
        );

        System.out.println(
                "Attributs sensibles avant configuration : " +
                definition.getSensitiveAttributes()
        );

        definition.setAttributeType(
                "age",
                AttributeType.QUASI_IDENTIFYING_ATTRIBUTE
        );

        definition.setAttributeType(
                "sex",
                AttributeType.QUASI_IDENTIFYING_ATTRIBUTE
        );

        definition.setAttributeType(
                "income",
                AttributeType.SENSITIVE_ATTRIBUTE
        );

        System.out.println(
                "QI après configuration : " +
                definition.getQuasiIdentifyingAttributes()
        );

        System.out.println(
                "Attributs sensibles après configuration : " +
                definition.getSensitiveAttributes()
        );

        // ----------------------------------------------------
        // 4. Vérification du DataHandle
        // ----------------------------------------------------

        System.out.println("\n=== DATA HANDLE ===");

        int numberOfColumns =
                data.getHandle().getNumColumns();

        System.out.println(
                "Nombre de colonnes : " + numberOfColumns
        );

        for (int i = 0; i < numberOfColumns; i++) {

            System.out.println(
                    i + " -> [" +
                    data.getHandle().getAttributeName(i) +
                    "]"
            );
        }

        // ----------------------------------------------------
        // 5. Vérification des colonnes
        // ----------------------------------------------------

        int ageIndex =
                data.getHandle().getColumnIndexOf("age");

        int sexIndex =
                data.getHandle().getColumnIndexOf("sex");

        int incomeIndex =
                data.getHandle().getColumnIndexOf("income");

        System.out.println(
                "Index age    = " + ageIndex
        );

        System.out.println(
                "Index sex    = " + sexIndex
        );

        System.out.println(
                "Index income = " + incomeIndex
        );

        if (ageIndex == -1) {
            throw new IllegalArgumentException(
                    "La colonne 'age' n'existe pas dans le DataHandle ARX."
            );
        }

        if (sexIndex == -1) {
            throw new IllegalArgumentException(
                    "La colonne 'sex' n'existe pas dans le DataHandle ARX."
            );
        }

        if (incomeIndex == -1) {
            throw new IllegalArgumentException(
                    "La colonne 'income' n'existe pas dans le DataHandle ARX."
            );
        }

        System.out.println(
                "OK : age, sex et income sont correctement chargés."
        );

        // ----------------------------------------------------
        // 6. Population de référence
        // ----------------------------------------------------

        ARXPopulationModel population =
                ARXPopulationModel.create(Region.USA);

        System.out.println(
                "Population : USA"
        );

        // ----------------------------------------------------
        // 7. Définition des QI
        // ----------------------------------------------------

        Set<String> qis = new HashSet<>();

        qis.add("age");
        qis.add("sex");

        System.out.println(
                "QI analysés : " + qis
        );

        // ----------------------------------------------------
        // 8. Risk estimator
        // ----------------------------------------------------

        RiskEstimateBuilder builder =
                data.getHandle().getRiskEstimator(
                        population,
                        qis
                );

        System.out.println(
                "Risk estimator créé."
        );

        // ----------------------------------------------------
        // 9. Population uniqueness
        // ----------------------------------------------------

        System.out.println(
                "\nCalcul de la population uniqueness..."
        );

        RiskModelPopulationUniqueness populationRisk =
                builder.getPopulationBasedUniquenessRisk();

        // ----------------------------------------------------
        // 10. Résultats
        // ----------------------------------------------------

        System.out.println(
                "\n=== POPULATION UNIQUENESS ==="
        );

        System.out.println(
                "Pitman : " +
                populationRisk.getFractionOfUniqueTuplesPitman()
        );

        System.out.println(
                "Zayatz : " +
                populationRisk.getFractionOfUniqueTuplesZayatz()
        );

        System.out.println(
                "SNB : " +
                populationRisk.getFractionOfUniqueTuplesSNB()
        );

        System.out.println(
                "\n=== FIN ==="
        );
    }
}

