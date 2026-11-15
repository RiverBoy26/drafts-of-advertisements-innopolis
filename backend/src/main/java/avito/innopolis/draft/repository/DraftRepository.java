package avito.innopolis.draft.repository;

import avito.innopolis.draft.entity.Draft;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DraftRepository extends JpaRepository<Draft,UUID> {
    @EntityGraph(attributePaths={"targetMc","analysis.sourceAd"}) List<Draft> findByAnalysis_IdOrderByCreatedAtAsc(UUID runId);
    @EntityGraph(attributePaths={"targetMc","analysis.sourceAd"}) Optional<Draft> findByIdAndAnalysis_SourceAd_User_Id(UUID id, UUID userId);
    @EntityGraph(attributePaths={"targetMc","analysis.sourceAd"}) List<Draft> findByAnalysis_SourceAd_User_IdAndCollectionStateOrderByCreatedAtDesc(UUID userId, String collectionState);
    @EntityGraph(attributePaths={"targetMc","analysis.sourceAd"}) List<Draft> findByAnalysis_SourceAd_User_IdOrderByCreatedAtDesc(UUID userId);
    @Query("select d.id from Draft d where d.analysis.sourceAd.user.id = :userId")
    List<UUID> findIdsByUserId(@Param("userId") UUID userId);
}
