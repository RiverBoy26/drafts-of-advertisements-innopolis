package avito.innopolis.draft.repository;

import avito.innopolis.draft.entity.Draft;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DraftRepository extends JpaRepository<Draft,UUID> {
    @EntityGraph(attributePaths={"targetMc"}) List<Draft> findByAnalysis_IdOrderByCreatedAtAsc(UUID runId);
    @EntityGraph(attributePaths={"targetMc"}) Optional<Draft> findByIdAndAnalysis_SourceAd_User_Id(UUID id, UUID userId);
}
