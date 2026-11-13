package avito.innopolis.analysis.dto;

import java.util.UUID;

public record ErrorView(
        UUID id,
        String stage,
        String code,
        String message
) {}
