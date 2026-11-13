package avito.innopolis.draft.dto;

import jakarta.validation.constraints.Size;
public record DraftPatch(@Size(max=255) String title,@Size(max=10000) String text) {}
