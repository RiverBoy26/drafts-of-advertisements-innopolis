package avito.innopolis.ml.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.ALWAYS)
public record MlDraft(
        Integer mcId,
        String title,
        String text
) {
}
