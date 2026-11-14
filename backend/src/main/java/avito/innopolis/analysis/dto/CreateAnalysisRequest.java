package avito.innopolis.analysis.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateAnalysisRequest(
        @NotBlank @Size(max = 10000) String description,
        @NotNull @Min(101) @Max(106) Integer mcId
) {}
