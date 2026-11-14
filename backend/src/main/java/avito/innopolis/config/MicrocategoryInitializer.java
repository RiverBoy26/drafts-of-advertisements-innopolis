package avito.innopolis.config;

import avito.innopolis.catalog.entity.Microcategory;
import avito.innopolis.catalog.repository.MicrocategoryRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.util.Map;

@Configuration
@EnableConfigurationProperties(MicrocategoryInitializer.CatalogProperties.class)
public class MicrocategoryInitializer {
    @ConfigurationProperties(prefix = "app.catalog")
    public record CatalogProperties(Map<Integer, String> microcategories) {}

    @Bean CommandLineRunner fillCatalog(MicrocategoryRepository repo, CatalogProperties properties){
        return args -> {
    if (properties.microcategories() == null || properties.microcategories().isEmpty()) {
        throw new IllegalStateException("Не настроены микрокатегории app.catalog.microcategories");
    }
    for (var entry : properties.microcategories().entrySet()) {
        Integer id = entry.getKey();
        String name = entry.getValue();
        if (id == null || name == null || name.isBlank()) {
            throw new IllegalStateException("У каждой микрокатегории должны быть mcId и название");
        }
        Microcategory category = repo.findById(id)
                .orElseGet(() -> new Microcategory(id, name));
        category.name = name;
        repo.save(category);
    }
};
}
}
