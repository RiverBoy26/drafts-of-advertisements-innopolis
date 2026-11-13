package avito.innopolis.common.dto;

import java.math.BigDecimal;
import java.util.UUID;

public record Classification(
        UUID categoryId,
        String categoryName,
        UUID microcategoryId,
        String microcategoryName,
        BigDecimal confidence,
        boolean confirmed,
        String source
) {
}
