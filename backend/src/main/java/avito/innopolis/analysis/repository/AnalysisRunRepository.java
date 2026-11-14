package avito.innopolis.analysis.repository;

import avito.innopolis.analysis.entity.AnalysisRun;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface AnalysisRunRepository extends JpaRepository<AnalysisRun,UUID> {
    @Override
    @EntityGraph(attributePaths={"sourceAd", "sourceAd.originalMc"})
    Optional<AnalysisRun> findById(UUID id);

    @EntityGraph(attributePaths={"sourceAd"})
    Optional<AnalysisRun> findByIdAndSourceAd_User_Id(UUID id,UUID userId);
    @EntityGraph(attributePaths={"sourceAd"})
    List<AnalysisRun> findBySourceAd_IdOrderByCreatedAtDesc(UUID sourceAdId);
}
