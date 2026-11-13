package avito.innopolis.analysis.dto;

import java.util.UUID;

public record ServiceView(
        UUID id,
        Integer mcId,
        String name,
        String sourceFragment,
        java.math.BigDecimal confidence,
        boolean confirmed
) {}
