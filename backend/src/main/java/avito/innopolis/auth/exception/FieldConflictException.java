package avito.innopolis.auth.exception;

public class FieldConflictException extends RuntimeException {
    private final String field;

    public FieldConflictException(String field, String message) {
        super(message);
        this.field = field;
    }

    public String getField() {
        return field;
    }
}
