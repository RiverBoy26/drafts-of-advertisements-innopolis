package avito.innopolis.catalog.service;

import avito.innopolis.catalog.entity.Microcategory;
import avito.innopolis.catalog.repository.MicrocategoryRepository;
import avito.innopolis.common.exception.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly=true)
public class CatalogService {
    private final MicrocategoryRepository repository;
    public CatalogService(MicrocategoryRepository repository) {
        this.repository=repository;
    }
    public List<Microcategory> list() {
        return repository.findAll().stream().sorted(java.util.Comparator.comparing(c->c.mcId)).toList();
    }
    public Microcategory require(int mcId) {
        return repository.findById(mcId).orElseThrow(()->new ApiException(HttpStatus.UNPROCESSABLE_ENTITY,"INVALID_MICROCATEGORY","Неизвестная микрокатегория: "+mcId));
    }
}
