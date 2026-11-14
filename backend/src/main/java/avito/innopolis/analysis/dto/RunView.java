package avito.innopolis.analysis.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record RunView(
        UUID id,
        UUID sourceAdId,
        String status,
        String stage,
        int progress,
        String modelVersion,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {}
