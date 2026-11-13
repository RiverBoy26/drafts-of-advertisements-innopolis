package avito.innopolis.analysis.repository;

import avito.innopolis.analysis.entity.DetectedService;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface DetectedServiceRepository extends JpaRepository<DetectedService,UUID> {
 @EntityGraph(attributePaths={"targetMc"}) List<DetectedService> findByAnalysis_IdOrderByCreatedAtAsc(UUID id);
}
