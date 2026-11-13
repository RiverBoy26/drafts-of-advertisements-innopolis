package avito.innopolis.analysis.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name="analysis_runs",indexes={@Index(name="idx_analysis_ad",columnList="source_ad_id")})
public class AnalysisRun {
    @Id
    @GeneratedValue(strategy=GenerationType.UUID)
    public UUID id;

    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="source_ad_id",nullable=false)
    public SourceAd sourceAd;

    @Column(nullable=false,length=32)
    public String status="queued";

    @Column(nullable=false,length=32)
    public String stage="preprocessing";

    @Column(nullable=false)
    public int progress=0;

    @Column(length=100)
    public String modelVersion;
    public OffsetDateTime startedAt;

    public OffsetDateTime finishedAt;

    @CreationTimestamp
    @Column(nullable=false,updatable=false)
    public OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(nullable=false)
    public OffsetDateTime updatedAt;
}
