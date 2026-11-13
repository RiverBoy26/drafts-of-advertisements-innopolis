package avito.innopolis.analysis.dto;

import jakarta.validation.constraints.*;
public record CreateSourceAdRequest(
        @NotBlank @Size(max=10000) String description,
        @NotNull @Min(101) @Max(106) Integer mcId
) {}
