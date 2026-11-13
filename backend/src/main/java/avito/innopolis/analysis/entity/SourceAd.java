package avito.innopolis.analysis.entity;

import avito.innopolis.auth.entity.User;
import avito.innopolis.catalog.entity.Microcategory;
import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name="source_ads", indexes={@Index(name="idx_source_ads_user",columnList="user_id")})
public class SourceAd {
    @Id
    @GeneratedValue(strategy=GenerationType.UUID)
    public UUID id;

    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="user_id",nullable=false)
    public User user;

    @Column(nullable=false,columnDefinition="text")
    public String description;

    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="original_mc_id",nullable=false)
    public Microcategory originalMc;

    @CreationTimestamp
    @Column(nullable=false,updatable=false)
    public OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(nullable=false)
    public OffsetDateTime updatedAt;
}
