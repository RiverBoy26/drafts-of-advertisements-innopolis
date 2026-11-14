package avito.innopolis.draft.entity;

import avito.innopolis.analysis.entity.DetectedService;
import jakarta.persistence.*;

import java.util.UUID;

@Entity
@Table(name="draft_evidence",uniqueConstraints=@UniqueConstraint(name="uk_draft_evidence",columnNames={"draft_id","detected_service_id"}))
public class DraftEvidence {
    @Id @GeneratedValue(strategy=GenerationType.UUID)
    public UUID id;
    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="draft_id",nullable=false)
    public Draft draft;
    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="detected_service_id",nullable=false)
    public DetectedService detectedService;
}
