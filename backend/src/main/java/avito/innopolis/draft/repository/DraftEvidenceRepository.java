package avito.innopolis.draft.repository;

import avito.innopolis.draft.entity.DraftEvidence;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface DraftEvidenceRepository extends JpaRepository<DraftEvidence,UUID> {
    void deleteByDraft_Id(UUID draftId);
}
