#[test]
fn a_fill_keeps_its_producer_in_the_same_final_submission() {
    let (forwarded, blocking, scratch) = (0x1000, 0x2000, 0x9000);
    let producer = vec![
        View::Put { dst: forwarded, len: 64, from: Some(scratch) },
        View::Put { dst: blocking, len: 64, from: None },
    ];
    let consumer = vec![
        View::Fill { src: forwarded, len: 32 },
        View::Fill { src: blocking, len: 32 },
    ];
    let blocked = |address, _| address == forwarded || address == blocking;
    let runs = [(false, producer), (false, consumer)];
    let moves = forwards(&runs, blocked);
    assert_eq!(moves, [(1, 0, scratch)], "the first fill can forward when both lists stay together");
    let fill = |src| Does::Fill { src, len: 32, asked: blocked(src, 32), to: true };
    let mut behind = None;
    let first_fill = if FORWARD_AFTER_CUT { forwarded } else { moves[0].2 };
    assert_eq!(plan(&[
        Does::Placed { dst: forwarded, src: 0x3000, len: 64 },
        Does::Placed { dst: blocking, src: 0x4000, len: 64 },
        fill(first_fill),
        fill(blocking),
    ], 2, true, &mut behind), Err(BEHIND_PLACED));
    assert_eq!(behind, Some((usize::from(!FORWARD_AFTER_CUT), if FORWARD_AFTER_CUT { 2 } else { 3 })));
    let [(owners, _), (readers, _)] = split(vec![0, 1], vec![0, 1], 1).unwrap();
    assert_eq!((owners, readers), (vec![0], vec![1]));
    assert!(forwards(&runs[1..], blocked).is_empty(), "the consumer group owns no producer scratch");
    assert_eq!(first_fill, forwarded, "a cut left a consumer referring to a different flight's upload storage");
}
