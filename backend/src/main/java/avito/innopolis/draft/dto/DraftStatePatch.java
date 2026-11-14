package avito.innopolis.draft.dto;

import jakarta.validation.constraints.NotBlank;

public record DraftStatePatch(@NotBlank String state) {}
