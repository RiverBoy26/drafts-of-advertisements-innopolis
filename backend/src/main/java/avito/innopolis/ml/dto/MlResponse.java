package avito.innopolis.ml.dto;

import java.util.List;

public record MlResponse(
        List<MlDraft> drafts
) {
}