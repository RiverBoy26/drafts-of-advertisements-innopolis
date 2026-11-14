package avito.innopolis.common.dto;

import java.util.Map;

public record ErrorBody(String code, String message, Map<String,Object> details, String requestId) {
}
