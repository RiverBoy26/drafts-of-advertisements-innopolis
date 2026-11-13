package avito.innopolis.common.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DraftDetails(
        UUID id,
        UUID serviceId,
        String title,
        String description,
        NamedCategory category,
        NamedCategory microcategory,
        String status,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
