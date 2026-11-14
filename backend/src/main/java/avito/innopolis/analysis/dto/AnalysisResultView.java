package avito.innopolis.analysis.dto;

import avito.innopolis.ml.dto.MlResponse;
import java.util.UUID;

public record AnalysisResultView(UUID id, String status, MlResponse result) {}
