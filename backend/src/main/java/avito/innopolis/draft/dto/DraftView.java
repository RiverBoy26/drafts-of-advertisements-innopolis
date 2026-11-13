package avito.innopolis.draft.dto;

import java.util.UUID;

public record DraftView(UUID id,int mcId,String title,String text,String status) {
}
