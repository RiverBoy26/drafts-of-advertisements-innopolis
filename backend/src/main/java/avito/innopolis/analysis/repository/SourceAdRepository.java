package avito.innopolis.analysis.repository;

import avito.innopolis.analysis.entity.SourceAd;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface SourceAdRepository extends JpaRepository<SourceAd,UUID> {
 @EntityGraph(attributePaths={"originalMc"}) Optional<SourceAd> findByIdAndUser_Id(UUID id, UUID userId);
 @EntityGraph(attributePaths={"originalMc"}) List<SourceAd> findByUser_IdOrderByCreatedAtDesc(UUID userId);
}
