package avito.innopolis.common.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DraftUpdated(
        UUID id,
        UUID serviceId,
        String title,
        String description,
        String status,
        OffsetDateTime updatedAt
) {
}
