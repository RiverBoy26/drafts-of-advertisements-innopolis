package avito.innopolis.common.dto;

import jakarta.validation.constraints.NotNull;

import java.util.UUID;

public record ClassificationRequest(UUID categoryId, UUID microcategoryId, @NotNull Boolean confirmed) {
}
