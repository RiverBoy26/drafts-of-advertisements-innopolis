package avito.innopolis.catalog.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name="microcategories")
public class Microcategory {
    @Id @Column(name="mc_id")
    public Integer mcId;
    @Column(nullable=false,unique=true,length=120)
    public String name;
 protected Microcategory(){}
 public Microcategory(int id,String name){this.mcId=id;this.name=name;}
}
