package avito.innopolis.common.dto;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record AnalysisView(
        UUID id,
        String status,
        String stage,
        int progress,
        String sourceText,
        String normalizedText,
        List<ServiceView> services,
        List<Object> errors,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
