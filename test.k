($define! $test
  ($vau (name expected . body) env
    (println "Testing" name "...")
    ($let ((result (eval (cons $sequence body) env)))
      ($if (equal? result expected)
        #inert
        (test-error name
                    "; expected:" expected
                    ", actual:" result)))))

; XXX: use a keyed variable when we have those.
($define! current-trace ())

($define! test-env (get-current-environment))

($define! get-trace
  ($lambda () (reverse current-trace)))

($define! reset-trace!
  ($lambda () ($set! test-env current-trace ())))

($define! trace
  ($lambda (x) ($set! test-env current-trace (cons x current-trace))))

($define! $trace-and-result
  ($vau (body . envoper) env
    (reset-trace!)
    ($let ((result (eval (cons $sequence body) ($if (null? envoper) env (car envoper)))))
      (list (get-trace) result))))

; Test with trace.
($define! $t/t
  ($vau (name expected-trace expected-result . body) env
    (println "Testing" name "...")
    ($let (((trace result) ((wrap $trace-and-result) body env)))
      ($define! error ())
      ($unless (equal? trace expected-trace)
        ($define! error (list* "wrong trace! expected:" expected-trace
                               "but got:" trace
                               error)))
      ($unless (equal? result expected-result)
        ($define! error (list* "wrong result! expected:" expected-result
                               "but got:" result
                               error)))
      ($unless (null? error)
        (apply test-error (list* name error))))))

; Tests BEGIN

; Let's begin by testing trace itself.

($test "trace initial state" () (get-trace))
($test "trace something" ("a") (trace "a") (get-trace))
($test "reset trace" () (reset-trace!) (get-trace))
($test "trace order" ("a" "b")
  (reset-trace!) (trace "a") (trace "b") (get-trace))
($test "$trace-and-result" (("a" "b") "c") ($trace-and-result ((trace "a") (trace "b") "c")))
($t/t "$t/t" ("a" "b") "c" (trace "a") (trace "b") "c")

; Kernel semantics proper.

($test "param tree matching" ("a" "b" "c" "d" ("e" "f"))
  ($define! (a (b c) d . e)
    (cons "a"
          (cons
            (cons "b" (cons "c" ()))
            (cons "d"
                  (cons "e" (cons "f" ()))))))
  (list a b c d e))

($test "param tree matching in $let" ("a" "b" "c" "d")
  ($let ((a "a")
         ((b c d) (list "b" "c" "d")))
    (list a b c d)))

($test "list, cdddr" ("d" "e") (cdddr (list "a" "b" "c" "d" "e")))

($test "call/cc result" "x"
  ($let/cc cc
    (trace "a")
    (apply (continuation->applicative cc) "x")
    (trace "b")
    "y"))

($t/t "call/cc trace" ("a") "xyz"
  (string-append
    "x"
    ($let/cc cc
        (trace "a")
        (apply-continuation cc "y")
        (trace "b")
        "w")
    "z"))

($test "simple extend-continuation" "outside inside"
  ($let/cc cc
    (apply-continuation
      (extend-continuation
        cc
        ($lambda x
          (string-append x " inside")))
      "outside")))

($t/t "guard-continuation, no guards"
  ("inner")
  "apply-cont-val inner return"
  ($let/cc cc
    ($let
      ((in-cont
         (extend-continuation
           (guard-continuation
             (list)
             cc
             (list))
           ($lambda x
             (trace "inner")
             (string-append x " inner return")))))
      (apply-continuation in-cont "apply-cont-val"))))

($t/t "non-diverting entry guard"
  ("intercept" "inner")
  "apply-cont-val modified inner return"
  ($let/cc cc
    ($let
      ((in-cont
         (extend-continuation
           (guard-continuation
             (list
               (list
                 cc
                 ($lambda (val divert)
                   (trace "intercept")
                   (string-append val " modified"))))
             cc
             (list))
           ($lambda x
             (trace "inner")
             (string-append x " inner return")))))
      (apply-continuation in-cont "apply-cont-val"))))

($t/t "diverting entry guard"
  ("intercept")
  "intercepted! outer"
  (string-append
    ($let/cc cc
      ($let
        ((in-cont
           (extend-continuation
             (guard-continuation
               (list
                 (list
                   cc
                   ($lambda (val divert)
                     (trace "intercept")
                     (apply divert "intercepted!"))))
               cc
               (list))
             ($lambda x
               (trace "inner")
               (string-append x " inner return")))))
        (apply-continuation in-cont "apply-cont-val")))
    " outer"))

; I don't think this is Kernel semantics (e.g. read, in 4.10.5, "an applicative
; must have a list of operands", but is this cool or what?
($test "combine with non-list operand" "ha!" (($lambda x x) . "ha!"))
($test "combine with improper list" ("a" . "b") (($lambda x x) "a" . "b"))
($test "combine: final cdr of improper list matches 'rest' formal" ("a" "b") (($lambda (x . y) (list x y)) "a" . "b"))
(println)
(println "All OK.")
