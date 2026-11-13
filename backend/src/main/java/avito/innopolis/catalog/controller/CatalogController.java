package avito.innopolis.catalog.controller;

import avito.innopolis.catalog.dto.Item;
import avito.innopolis.catalog.service.CatalogService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/catalog")
public class CatalogController {

    private final CatalogService catalogService;

    public CatalogController(CatalogService catalogService) {
        this.catalogService = catalogService;
    }

    @GetMapping("/microcategories")
    public Map<String, List<Item>> list() {
        List<Item> items = catalogService.list().stream()
                .map(microcategory -> new Item(microcategory.mcId, microcategory.name))
                .toList();
        return Map.of("items", items);
    }
}
