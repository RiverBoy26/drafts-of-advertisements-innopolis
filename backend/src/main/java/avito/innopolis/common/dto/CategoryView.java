package avito.innopolis.common.dto;

import java.util.List;
import java.util.UUID;

public record CategoryView(UUID id, String name, UUID parentId, String type, List<String> path) {
}
