package avito.innopolis.analysis.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record AdView(
        UUID id,
        String description,
        Integer mcId,
        OffsetDateTime createdAt
) {}
