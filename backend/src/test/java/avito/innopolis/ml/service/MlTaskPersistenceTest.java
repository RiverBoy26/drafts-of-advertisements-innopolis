package avito.innopolis.ml.service;

import avito.innopolis.analysis.entity.AnalysisRun;
import avito.innopolis.analysis.entity.SourceAd;
import avito.innopolis.auth.entity.User;
import avito.innopolis.catalog.entity.Microcategory;
import avito.innopolis.ml.dto.MlResponse;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

@DataJpaTest(properties = {
        "spring.sql.init.mode=never",
        "spring.jpa.hibernate.ddl-auto=create-drop"
})
@Import({MlTaskPersistence.class, MlResultValidator.class})
class MlTaskPersistenceTest {

    @Autowired EntityManager entityManager;
    @Autowired MlTaskPersistence persistence;

    @Test
    void loadsOriginalMicrocategoryForBackgroundTask() {
        User user = new User();
        user.setFirstName("Test");
        user.setLastName("User");
        user.setEmail("test@example.com");
        user.setPasswordHash("hash");
        entityManager.persist(user);

        Microcategory category = new Microcategory(101, "Ремонт под ключ");
        entityManager.persist(category);

        SourceAd ad = new SourceAd();
        ad.user = user;
        ad.description = "Ремонт квартир";
        ad.originalMc = category;
        entityManager.persist(ad);

        AnalysisRun run = new AnalysisRun();
        run.sourceAd = ad;
        entityManager.persist(run);
        entityManager.flush();
        entityManager.clear();

        var request = persistence.begin(run.id);
        assertEquals("Ремонт квартир", request.description());
        assertEquals(101, request.mcId());

        persistence.completed(run.id, new MlResponse(List.of()));
        entityManager.flush();
    }
}
