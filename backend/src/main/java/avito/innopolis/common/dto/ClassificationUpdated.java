package avito.innopolis.common.dto;

import java.util.UUID;

public record ClassificationUpdated(
        UUID serviceId,
        Classification classification,
        boolean draftRequiresRegeneration
) {
}
