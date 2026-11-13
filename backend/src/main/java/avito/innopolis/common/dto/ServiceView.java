package avito.innopolis.common.dto;

import java.util.List;
import java.util.UUID;

public record ServiceView(
        UUID id,
        String name,
        String sourceFragment,
        Classification classification,
        List<DraftView> drafts
) {
}
