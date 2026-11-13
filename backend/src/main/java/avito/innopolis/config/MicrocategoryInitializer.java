package avito.innopolis.config;

import avito.innopolis.catalog.entity.Microcategory;
import avito.innopolis.catalog.repository.MicrocategoryRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MicrocategoryInitializer {
    @Bean CommandLineRunner fillCatalog(MicrocategoryRepository repo){
        return args -> {
    String[] names= {
        "Ремонт под ключ","Штукатурные работы","Плиточные работы","Сантехника","Электрика","Поклейка обоев и малярные работы"
    };
    for(int i=0;i<names.length;i++) {
        int id=101+i;
        if(!repo.existsById(id))repo.save(new Microcategory(id,names[i]));
    }
};
}
}
