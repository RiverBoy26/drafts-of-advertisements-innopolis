package avito.innopolis.common.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DraftView(
        UUID id,
        UUID serviceId,
        String title,
        String description,
        String status,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
