package avito.innopolis.draft.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DraftView(UUID id,UUID analysisId,UUID sourceAdId,String sourceDescription,int mcId,String title,String text,String status,String collectionState,OffsetDateTime createdAt,OffsetDateTime updatedAt) {
}
