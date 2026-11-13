package avito.innopolis.common.dto;

import java.util.List;

public record CatalogPage(List<CategoryView> items, String nextCursor) {
}
