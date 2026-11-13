package avito.innopolis.common.dto;

import java.util.UUID;

public record ExportItem(
        UUID draftId,
        String title,
        String description,
        String category,
        String microcategory
) {
}
